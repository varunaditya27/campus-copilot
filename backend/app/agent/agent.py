import json
import operator
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Annotated, Literal

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.agent.domains import SPECIALIST_PROMPTS, allowed_tools, schemas_for
from app.agent.prompts import (
    KNOWLEDGE_UNAVAILABLE_MESSAGE,
    PLANNER_PROMPT,
    SYSTEM_PROMPT,
    build_context_message,
    build_entities_message,
    build_plan_message,
    build_student_message,
)
from app.actions.base import ActionError
from app.actions.registry import ACTIONS
from app.agent.tool_registry import STUDENT_TOOLS, TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.config import AGENT_PLANNING
from app.core.errors import AppError
from app.llm import BaseLLMClient, get_llm_client
from app.llm.base import collect
from app.llm.tiers import tier_for
from app.models.auth import CurrentStudent
from app.models.memory import Entity
from app.models.actions import Confirmation
from app.models.chat import ChatHistoryItem, ChatResponse, Source, ToolActivityEntry
from app.rag.retriever import KnowledgeBaseNotFound, retrieve
from app.services import action_service

MAX_TOOL_ROUNDS = 4

TOOL_LABELS = {
    "search_events": "Searching campus events",
    "check_event_availability": "Checking event availability",
    "calculate_attendance": "Calculating attendance",
    "get_attendance_report": "Checking your attendance records",
    "get_cgpa": "Calculating your CGPA",
    "get_student_timetable": "Looking up your timetable",
    "get_exam_schedule": "Checking your exam schedule",
    "get_elective_options": "Listing your elective options",
    "get_fee_dues": "Checking your fee dues",
    "get_course_info": "Looking up the course",
    "get_faculty_profile": "Looking up the faculty member",
    "check_library_availability": "Checking the library catalogue",
    "get_canteen_menu": "Looking up the canteen menu",
    "get_bus_schedule": "Checking the shuttle schedule",
    "get_lost_and_found": "Searching lost and found",
    "check_study_room_availability": "Checking study room availability",
    "get_grievance_status": "Checking your grievances",
    "get_counselling_slots": "Looking up counselling slots",
    "get_placement_drives": "Looking up placement drives",
    "check_placement_eligibility": "Checking placement eligibility",
    "get_event_detail": "Looking up the event",
    "get_my_registrations": "Checking your registrations",
    "get_event_feedback_form": "Opening the feedback form",
}


def _summarize(tool: str, result: dict) -> str:
    if "error" in result:
        return result["error"]
    if tool == "search_events":
        return f"Found {len(result)} matching events"
    if tool == "check_event_availability":
        return f"{result['remaining_seats']} seats available" if result["available"] else "No seats available"
    if tool == "calculate_attendance":
        return f"{result['percentage']}% attendance"
    if tool == "get_attendance_report":
        low = len(result["below_required"])
        return f"{low} of {len(result['courses'])} subjects below 75%" if low else "All subjects at 75% or above"
    if tool == "get_cgpa":
        return f"CGPA {result['cgpa']}" if result["cgpa"] is not None else "No results yet"
    if tool == "get_student_timetable":
        if "week" in result:
            return f"{sum(len(d['classes']) for d in result['week'])} classes this week"
        return f"{len(result['classes'])} classes on {result['day']}"
    if tool == "get_exam_schedule":
        upcoming = sum(e["status"] != "past" for e in result["exams"])
        return f"{upcoming} upcoming of {len(result['exams'])} exams"
    if tool == "get_elective_options":
        return f"{len(result['electives'])} electives in semester {result['semester']}"
    if tool == "get_fee_dues":
        return f"{result['total_outstanding']} rupees outstanding" if result["total_outstanding"] else "No fees outstanding"
    if tool == "get_course_info":
        return f"{result['course_code']} {result['name']}"
    if tool == "check_library_availability":
        first = result["books"][0]
        return f"{first['title']}: {first['status'].replace('_', ' ')}" + (f" (+{len(result['books']) - 1} more)" if len(result["books"]) > 1 else "")
    if tool == "get_canteen_menu":
        return f"{sum(len(m['items']) for m in result['meals'])} items on {result['day']}" if result["meals"] else result["message"]
    if tool == "get_bus_schedule":
        return f"{len(result['routes'])} routes, {sum(r['runs_today'] for r in result['routes'])} running today"
    if tool == "get_lost_and_found":
        return f"{len(result['items'])} matching items"
    if tool == "check_study_room_availability":
        return f"{sum(bool(r['free_slots']) for r in result['rooms'])} rooms with free slots on {result['date']}"
    if tool == "get_grievance_status":
        return result.get("status", f"{len(result.get('tickets', []))} tickets") if "ticket" not in result else f"{result['ticket']}: {result['status']}"
    if tool == "get_counselling_slots":
        return f"{len(result['slots'])} free slots"
    if tool == "get_placement_drives":
        return f"{len(result['drives'])} upcoming drives"
    if tool == "check_placement_eligibility":
        return "Matches several drives" if "matches" in result else ("Eligible" if result["eligible"] else "Not eligible")
    if tool == "get_event_detail":
        return f"{result['name']}: {result['seats_left']} seats left"
    if tool == "get_my_registrations":
        return f"{len(result['registrations'])} registrations, {len(result['waitlisted'])} waitlisted"
    if tool == "get_event_feedback_form":
        return "Feedback open" if result["can_submit"] else "Feedback not available"
    if tool == "get_faculty_profile":
        return result["name"] if "name" in result else f"{len(result['matches'])} possible matches"
    return "Done"


def _parse_arguments(raw: str) -> dict | None:
    try:
        args = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return args if isinstance(args, dict) else None


def _describe_validation_error(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}" for e in exc.errors()
    )


def _run_tool(
    name: str, raw_arguments: str, student: CurrentStudent, allowed: frozenset[str] | None = None
) -> tuple[dict | list, str]:
    if allowed is not None and name not in allowed:
        return {"error": f"The tool {name} is not available to you here."}, "error"
    args = _parse_arguments(raw_arguments)
    if args is None:
        return {"error": "Tool arguments were not a valid JSON object"}, "error"
    if name in STUDENT_TOOLS:
        args = {**{k: v for k, v in args.items() if k != "student_id"}, "student_id": student.student_id}
    try:
        return TOOL_FUNCTIONS[name](**args), "done"
    except ValidationError as exc:
        return {"error": _describe_validation_error(exc)}, "error"
    except Exception as exc:
        return {"error": str(exc)}, "error"


def _event(kind: str, **payload) -> dict:
    return {"type": kind, "payload": payload}


def _stream_completion(
    client: BaseLLMClient,
    messages: list[dict],
    emit: Callable[[dict], None],
    tools: list[dict] | None = TOOL_SCHEMAS,
    tier: str = "balanced",
) -> tuple[str, list[dict]]:
    """Stream one model round, calling emit with a token event for each piece of
    text as it arrives. Returns the full text and the list of complete tool calls."""
    completion = collect(
        client.stream_completion(messages, tools, tier), on_text=lambda text: emit(_event("token", text=text))
    )
    return completion.text, completion.tool_calls


# --- the agent as a graph
#
#   retrieve -> (plan) -> reason --+--> respond            (the model answered)
#                           ^      +--> request_confirmation -> respond
#                           |      +--> execute_tools --+--> reason  (feed results back)
#                           +----------------------------+--> respond (out of rounds)
#
# Nodes report progress as events through LangGraph's stream writer; the events
# are the same ones the frontend has always received.


@dataclass
class AgentState:
    message: str
    student: CurrentStudent
    history: list[ChatHistoryItem] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    chunks: list[dict] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    # Messages are only ever added to, so each node returns just what it adds.
    messages: Annotated[list[dict], operator.add] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    draft: str = ""  # text the model wrote before asking for tools
    tool_activity: Annotated[list[ToolActivityEntry], operator.add] = field(default_factory=list)
    pending_confirmation: Confirmation | None = None
    reply: str | None = None
    loop_count: int = 0
    domain: str | None = None  # a specialist's domain; None for the single agent with every tool
    quality: str | None = None  # a quality tier the student asked for; None lets the agent choose


MAX_PARALLEL_TOOLS = 8
OUT_OF_ROUNDS_REPLY = "I wasn't able to finish that request in a reasonable number of steps."

# A safety net behind MAX_TOOL_ROUNDS: LangGraph stops a run that takes more
# steps than this, so a mistake in the routing cannot loop forever.
RECURSION_LIMIT = MAX_TOOL_ROUNDS * 2 + 8


def _activity(call: dict, result: dict | list, status: str) -> ToolActivityEntry:
    return ToolActivityEntry(
        id=call["id"],
        tool=call["name"],
        label=TOOL_LABELS.get(call["name"], call["name"]),
        status=status,
        resultSummary=_summarize(call["name"], result),
    )


def retrieve_node(state: AgentState) -> dict:
    emit = get_stream_writer()
    knowledge_unavailable = False
    try:
        chunks = retrieve(state.message)
    except KnowledgeBaseNotFound:
        chunks = []
        knowledge_unavailable = True

    emit(_event("rag_context", sources=[s.model_dump() for s in _sources(chunks)]))

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_student_message(state.student)},
    ]
    if state.domain:
        messages.insert(1, {"role": "system", "content": SPECIALIST_PROMPTS[state.domain]})
    if state.entities:
        messages.append({"role": "system", "content": build_entities_message(state.entities)})
    messages += [{"role": h.role, "content": h.content} for h in state.history]
    if chunks:
        messages.append({"role": "system", "content": build_context_message(chunks)})
    elif knowledge_unavailable:
        messages.append({"role": "system", "content": KNOWLEDGE_UNAVAILABLE_MESSAGE})
    messages.append({"role": "user", "content": state.message})
    return {"chunks": chunks, "messages": messages}


def _parse_plan(text: str) -> list[str]:
    try:
        steps = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(steps, list):
        return []
    return [s.strip()[:200] for s in steps if isinstance(s, str) and s.strip()][:6]


def plan_node(state: AgentState) -> dict:
    """Ask the model for an ordered list of steps, and show it to the model as a plan."""
    text, _ = _stream_completion(
        get_llm_client(),
        [{"role": "system", "content": PLANNER_PROMPT}, {"role": "user", "content": state.message}],
        emit=lambda event: None,
        tools=None,
        tier=tier_for(state.quality, agentic=False),
    )
    steps = _parse_plan(text)
    if not steps:
        return {}
    return {"plan": steps, "messages": [{"role": "system", "content": build_plan_message(steps)}]}


def reason_node(state: AgentState) -> dict:
    """One model call: it answers, or asks for tools."""
    emit = get_stream_writer()
    # A plan, or tools already run with their results being worked through, means a multi-step task.
    tier = tier_for(state.quality, agentic=bool(state.plan) or state.loop_count > 0)
    text, tool_calls = _stream_completion(get_llm_client(), state.messages, emit, schemas_for(state.domain), tier)
    if tool_calls and text:
        emit(_event("reset"))  # the text so far was only a preamble to the tool calls
    update: dict = {"tool_calls": tool_calls, "draft": text, "loop_count": state.loop_count + 1}
    if not tool_calls:
        update["reply"] = text
    return update


def request_confirmation_node(state: AgentState) -> dict:
    """Turn the model's request for an action (such as registering) into a
    confirmation for the student to approve. Nothing is done here."""
    emit = get_stream_writer()
    allowed = allowed_tools(state.domain)
    call = next(c for c in state.tool_calls if c["name"] in ACTIONS and (allowed is None or c["name"] in allowed))
    try:
        confirmation = action_service.propose(state.student, call["name"], _parse_arguments(call["arguments"]) or {})
        reply = f"I've prepared this for you: {confirmation.title}. Please confirm below to complete it."
    except ActionError as exc:
        confirmation, reply = None, str(exc)
    emit(_event("token", text=reply))
    return {"pending_confirmation": confirmation, "reply": reply, "tool_calls": []}


def _run_tools(
    calls: list[dict], emit: Callable[[dict], None], student: CurrentStudent, allowed: frozenset[str] | None = None
) -> tuple[list[ToolActivityEntry], list[tuple[dict | list, str]]]:
    """Run the tool calls, side by side when there are several. Events are sent from
    this thread only (the stream writer belongs to it); results keep the order of the calls."""
    for call in calls:
        emit(_event("tool_start", id=call["id"], tool=call["name"], label=TOOL_LABELS.get(call["name"], call["name"])))

    outcomes: list[tuple[dict | list, str] | None] = [None] * len(calls)
    entries: list[ToolActivityEntry | None] = [None] * len(calls)

    def finish(index: int, outcome: tuple[dict | list, str]) -> None:
        outcomes[index] = outcome
        entries[index] = _activity(calls[index], *outcome)
        emit(_event("tool_done", **entries[index].model_dump()))

    if len(calls) == 1:
        finish(0, _run_tool(calls[0]["name"], calls[0]["arguments"], student, allowed))
    else:
        with ThreadPoolExecutor(max_workers=min(len(calls), MAX_PARALLEL_TOOLS)) as pool:
            futures = {pool.submit(_run_tool, c["name"], c["arguments"], student, allowed): i for i, c in enumerate(calls)}
            for future in as_completed(futures):
                finish(futures[future], future.result())
    return entries, outcomes


def execute_tools_node(state: AgentState) -> dict:
    emit = get_stream_writer()
    calls = state.tool_calls
    entries, outcomes = _run_tools(calls, emit, state.student, allowed_tools(state.domain))

    messages = [
        {
            "role": "assistant",
            "content": state.draft or None,
            "tool_calls": [
                {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                for c in calls
            ],
        }
    ]
    messages += [
        {"role": "tool", "tool_call_id": c["id"], "name": c["name"], "content": json.dumps(result)}
        for c, (result, _) in zip(calls, outcomes)
    ]
    update: dict = {"messages": messages, "tool_activity": entries, "tool_calls": []}
    if state.loop_count >= MAX_TOOL_ROUNDS:
        emit(_event("token", text=OUT_OF_ROUNDS_REPLY))
        update["reply"] = OUT_OF_ROUNDS_REPLY
    return update


def respond_node(state: AgentState) -> dict:
    response = ChatResponse(
        reply=state.reply or "",
        sources=_sources(state.chunks),
        toolActivity=state.tool_activity or None,
        confirmation=state.pending_confirmation,
    )
    get_stream_writer()(_event("done", **response.model_dump(mode="json")))
    return {}


def _sources(chunks: list[dict]) -> list[Source]:
    return [Source(document=c["document"], section=c["section"], snippet=c["snippet"]) for c in chunks]


# --- the decisions the graph makes


def is_confirmation_needed(state: AgentState) -> bool:
    """The model proposed an action, which only the student can approve."""
    allowed = allowed_tools(state.domain)
    return any(call["name"] in ACTIONS and (allowed is None or call["name"] in allowed) for call in state.tool_calls)


def should_call_tools(state: AgentState) -> bool:
    return bool(state.tool_calls)


def is_done(state: AgentState) -> bool:
    """The model has answered, or the allowed rounds are used up."""
    return state.reply is not None


def route_after_reason(state: AgentState) -> Literal["request_confirmation", "execute_tools", "respond"]:
    if is_confirmation_needed(state):
        return "request_confirmation"
    if should_call_tools(state):
        return "execute_tools"
    return "respond"


def route_after_tools(state: AgentState) -> Literal["reason", "respond"]:
    return "respond" if is_done(state) else "reason"


def build_graph(planning: bool = AGENT_PLANNING):
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("reason", reason_node)
    graph.add_node("execute_tools", execute_tools_node)
    graph.add_node("request_confirmation", request_confirmation_node)
    graph.add_node("respond", respond_node)

    graph.add_edge(START, "retrieve")
    if planning:
        graph.add_node("plan", plan_node)
        graph.add_edge("retrieve", "plan")
        graph.add_edge("plan", "reason")
    else:
        graph.add_edge("retrieve", "reason")
    graph.add_conditional_edges("reason", route_after_reason, ["request_confirmation", "execute_tools", "respond"])
    graph.add_edge("request_confirmation", "respond")
    graph.add_conditional_edges("execute_tools", route_after_tools, ["reason", "respond"])
    graph.add_edge("respond", END)
    return graph.compile()


_graph = build_graph()


def run_agent_stream(
    message: str,
    history: list[ChatHistoryItem],
    student: CurrentStudent,
    entities: list[Entity] | None = None,
    quality: str | None = None,
) -> Iterator[dict]:
    """Run the agent for a signed-in student, yielding typed events as it goes.

    Event types: rag_context, token, reset (discard the text streamed so far,
    because the model is about to call a tool), tool_start, tool_done, and
    finally done, whose payload is the complete ChatResponse. Failures raise
    AppError.
    """
    state = AgentState(message=message, student=student, history=history, entities=entities or [], quality=quality)
    config = {"recursion_limit": RECURSION_LIMIT}
    for part in _graph.stream(state, config, stream_mode="custom", version="v2"):
        yield part["data"]


def run_agent(
    message: str,
    history: list[ChatHistoryItem],
    student: CurrentStudent,
    entities: list[Entity] | None = None,
    quality: str | None = None,
) -> ChatResponse:
    """The same run without streaming: wait for the final event."""
    events = list(run_agent_stream(message, history, student, entities, quality))
    return ChatResponse.model_validate(events[-1]["payload"])


def complete_text(messages: list[dict], tier: str = "balanced") -> str:
    """A single model answer to the messages, with no tools. Model failures raise AppError."""
    text, _ = _stream_completion(get_llm_client(), messages, emit=lambda event: None, tools=None, tier=tier)
    return text.strip()

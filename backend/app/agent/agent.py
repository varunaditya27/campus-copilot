import json
import operator
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Annotated, Literal

from groq import APIError, APIStatusError, BadRequestError, RateLimitError
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.agent.prompts import (
    KNOWLEDGE_UNAVAILABLE_MESSAGE,
    PLANNER_PROMPT,
    SYSTEM_PROMPT,
    build_context_message,
    build_plan_message,
    build_student_message,
)
from app.agent.tool_registry import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.config import AGENT_PLANNING, GROQ_MODEL
from app.core.errors import AppError
from app.core.groq_client import get_groq_client
from app.models.auth import CurrentStudent
from app.models.chat import (
    ChatHistoryItem,
    ChatResponse,
    ConfirmationEvent,
    RegistrationConfirmation,
    Source,
    ToolActivityEntry,
)
from app.rag.retriever import KnowledgeBaseNotFound, retrieve
from app.services import event_service

MAX_TOOL_ROUNDS = 4

# Groq documents 413 for an oversized request but no specific code for an
# over-long prompt, so a 400 is matched by its message wording as well.
_CONTEXT_TOO_LONG_HINTS = ("context length", "reduce the length", "too long")

TOOL_LABELS = {
    "search_events": "Searching campus events",
    "check_event_availability": "Checking event availability",
    "calculate_attendance": "Calculating attendance",
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


def _run_tool(name: str, raw_arguments: str) -> tuple[dict | list, str]:
    args = _parse_arguments(raw_arguments)
    if args is None:
        return {"error": "Tool arguments were not a valid JSON object"}, "error"
    try:
        return TOOL_FUNCTIONS[name](**args), "done"
    except ValidationError as exc:
        return {"error": _describe_validation_error(exc)}, "error"
    except Exception as exc:
        return {"error": str(exc)}, "error"


def _to_app_error(exc: APIError) -> AppError:
    if isinstance(exc, RateLimitError):
        return AppError(
            429, "rate_limited", "The AI service is busy right now. Please try again in a moment."
        )
    too_long = (isinstance(exc, APIStatusError) and exc.status_code == 413) or (
        isinstance(exc, BadRequestError)
        and any(hint in exc.message.lower() for hint in _CONTEXT_TOO_LONG_HINTS)
    )
    if too_long:
        return AppError(
            413, "context_too_long", "This conversation is too long. Please start a new chat."
        )
    return AppError(
        502, "llm_unavailable", "The AI service is unavailable right now. Please try again shortly."
    )


def _event(kind: str, **payload) -> dict:
    return {"type": kind, "payload": payload}


def _stream_completion(
    client, messages: list[dict], emit: Callable[[dict], None], tools: list[dict] | None = TOOL_SCHEMAS
) -> tuple[str, list[dict]]:
    """Stream one model round, calling emit with a token event for each piece of
    text as it arrives.

    The model's tool calls arrive as fragments (an id and name first, then the
    JSON arguments in pieces), so they are reassembled by index. Returns the
    full text and the list of complete tool calls.
    """
    text_parts: list[str] = []
    calls: dict[int, dict] = {}
    options = {"tools": tools, "tool_choice": "auto"} if tools else {}
    try:
        stream = client.chat.completions.create(model=GROQ_MODEL, messages=messages, stream=True, **options)
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                text_parts.append(delta.content)
                emit(_event("token", text=delta.content))
            for part in delta.tool_calls or []:
                call = calls.setdefault(part.index, {"id": None, "name": "", "arguments": ""})
                if part.id:
                    call["id"] = part.id
                if part.function:
                    if part.function.name:
                        call["name"] = part.function.name
                    if part.function.arguments:
                        call["arguments"] += part.function.arguments
    except APIError as exc:
        raise _to_app_error(exc) from exc

    tool_calls = [
        {**calls[index], "id": calls[index]["id"] or f"call_{index}"} for index in sorted(calls)
    ]
    return "".join(text_parts), tool_calls


def _confirmation_for(args: dict, student: CurrentStudent) -> RegistrationConfirmation | None:
    event = event_service.get_event(args.get("event_id", ""))
    if event is None:
        return None
    return RegistrationConfirmation(
        event=ConfirmationEvent(
            id=event.id, name=event.name, date=event.date, time=event.time, venue=event.venue
        ),
        studentId=student.student_id,
    )


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
    chunks: list[dict] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    # Messages are only ever added to, so each node returns just what it adds.
    messages: Annotated[list[dict], operator.add] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    draft: str = ""  # text the model wrote before asking for tools
    tool_activity: Annotated[list[ToolActivityEntry], operator.add] = field(default_factory=list)
    pending_confirmation: RegistrationConfirmation | None = None
    reply: str | None = None
    loop_count: int = 0


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
        get_groq_client(),
        [{"role": "system", "content": PLANNER_PROMPT}, {"role": "user", "content": state.message}],
        emit=lambda event: None,
        tools=None,
    )
    steps = _parse_plan(text)
    if not steps:
        return {}
    return {"plan": steps, "messages": [{"role": "system", "content": build_plan_message(steps)}]}


def reason_node(state: AgentState) -> dict:
    """One model call: it answers, or asks for tools."""
    emit = get_stream_writer()
    text, tool_calls = _stream_completion(get_groq_client(), state.messages, emit)
    if tool_calls and text:
        emit(_event("reset"))  # the text so far was only a preamble to the tool calls
    update: dict = {"tool_calls": tool_calls, "draft": text, "loop_count": state.loop_count + 1}
    if not tool_calls:
        update["reply"] = text
    return update


def request_confirmation_node(state: AgentState) -> dict:
    """Turn the model's request to register into a confirmation for the student to
    approve. Nothing is registered here."""
    emit = get_stream_writer()
    register_call = next(c for c in state.tool_calls if c["name"] == "register_for_event")
    confirmation = _confirmation_for(_parse_arguments(register_call["arguments"]) or {}, state.student)
    reply = (
        f"I've prepared a registration for {confirmation.event.name}. "
        "Please confirm below to complete it."
        if confirmation
        else "I couldn't find that event to register you for -- could you "
        "confirm which event you mean?"
    )
    emit(_event("token", text=reply))
    return {"pending_confirmation": confirmation, "reply": reply, "tool_calls": []}


def _run_tools(
    calls: list[dict], emit: Callable[[dict], None]
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
        finish(0, _run_tool(calls[0]["name"], calls[0]["arguments"]))
    else:
        with ThreadPoolExecutor(max_workers=min(len(calls), MAX_PARALLEL_TOOLS)) as pool:
            futures = {pool.submit(_run_tool, c["name"], c["arguments"]): i for i, c in enumerate(calls)}
            for future in as_completed(futures):
                finish(futures[future], future.result())
    return entries, outcomes


def execute_tools_node(state: AgentState) -> dict:
    emit = get_stream_writer()
    calls = state.tool_calls
    entries, outcomes = _run_tools(calls, emit)

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
    get_stream_writer()(_event("done", **response.model_dump()))
    return {}


def _sources(chunks: list[dict]) -> list[Source]:
    return [Source(document=c["document"], section=c["section"], snippet=c["snippet"]) for c in chunks]


# --- the decisions the graph makes


def is_confirmation_needed(state: AgentState) -> bool:
    """The model asked to register someone, which must be confirmed by the student first."""
    return any(call["name"] == "register_for_event" for call in state.tool_calls)


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
    message: str, history: list[ChatHistoryItem], student: CurrentStudent
) -> Iterator[dict]:
    """Run the agent for a signed-in student, yielding typed events as it goes.

    Event types: rag_context, token, reset (discard the text streamed so far,
    because the model is about to call a tool), tool_start, tool_done, and
    finally done, whose payload is the complete ChatResponse. Failures raise
    AppError.
    """
    state = AgentState(message=message, student=student, history=history)
    config = {"recursion_limit": RECURSION_LIMIT}
    for part in _graph.stream(state, config, stream_mode="custom", version="v2"):
        yield part["data"]


def run_agent(
    message: str, history: list[ChatHistoryItem], student: CurrentStudent
) -> ChatResponse:
    """The same run without streaming: wait for the final event."""
    events = list(run_agent_stream(message, history, student))
    return ChatResponse.model_validate(events[-1]["payload"])

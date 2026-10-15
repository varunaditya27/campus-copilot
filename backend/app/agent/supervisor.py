import json
import operator
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Annotated

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.agent import agent
from app.agent.domains import DOMAIN_DESCRIPTIONS, DOMAIN_TOOLS
from app.core.config import MULTI_AGENT
from app.core.errors import AppError
from app.llm.tiers import tier_for
from app.models.auth import CurrentStudent
from app.models.chat import ChatHistoryItem, ChatResponse, Source
from app.models.memory import Entity
from app.observability.logging import get_logger

MAX_DOMAINS = 3

logger = get_logger(__name__)
ROUTER_HISTORY_ITEMS = 4
ROUTER_HISTORY_CHARS = 300

ROUTER_PROMPT = (
    "You route a student's message at a college campus to specialist assistants. The specialists are:\n"
    + "\n".join(f"- {name}: {description}" for name, description in DOMAIN_DESCRIPTIONS.items())
    + f"\n\nReply with ONLY a JSON array of one to {MAX_DOMAINS} specialist names, most relevant first. Use more than one "
    "only when the message really asks for things from different specialists. A greeting or a general question about "
    'campus rules goes to "general". Example: ["events", "academic"]'
)

MERGE_PROMPT = (
    "You combine answers from specialist assistants into one reply to a student. Keep every fact, figure and instruction "
    "exactly as given and invent nothing. Write one short, well-organised answer without mentioning specialists. If an "
    "answer says something is waiting for the student to confirm, say so."
)


def parse_domains(text: str) -> list[str]:
    """The domains named in the router's reply, in order, without repeats; empty if unusable."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match is None:
        return []
    try:
        names = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(names, list):
        return []
    seen: list[str] = []
    for name in names:
        if isinstance(name, str) and name.strip().lower() in DOMAIN_TOOLS and name.strip().lower() not in seen:
            seen.append(name.strip().lower())
    return seen[:MAX_DOMAINS]


def route(message: str, history: list[ChatHistoryItem]) -> list[str]:
    """Ask the model which specialists should handle the message. Empty means it could not
    tell, and the single agent with every tool takes the message instead."""
    recent = "\n".join(f"{h.role}: {h.content[:ROUTER_HISTORY_CHARS]}" for h in history[-ROUTER_HISTORY_ITEMS:])
    prompt = (f"Recent conversation:\n{recent}\n\n" if recent else "") + f"Message to route: {message}"
    text, _ = agent._stream_completion(
        agent.get_llm_client(),
        [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": prompt}],
        emit=lambda event: None,
        tools=None,
        tier="fast",  # sorting a message into five domains is the easy part
    )
    return parse_domains(text)


@dataclass
class SupervisorState:
    message: str
    student: CurrentStudent
    history: list[ChatHistoryItem] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    quality: str | None = None
    domains: list[str | None] = field(default_factory=list)  # None means the single agent
    results: Annotated[list[tuple[int, str | None, ChatResponse]], operator.add] = field(default_factory=list)


def router_node(state: SupervisorState) -> dict:
    domains = route(state.message, state.history) or [None]
    logger.info("agent.route", domains=domains)
    return {"domains": domains}


def fan_out(state: SupervisorState) -> list[Send]:
    return [
        Send(
            "specialist",
            {
                "index": index,
                "domain": domain,
                "alone": len(state.domains) == 1,
                "message": state.message,
                "student": state.student,
                "history": state.history,
                "entities": state.entities,
                "quality": state.quality,
            },
        )
        for index, domain in enumerate(state.domains)
    ]


def specialist_node(task: dict) -> dict:
    """Run one specialist: the ordinary agent graph, limited to its domain's tools.

    A lone specialist streams exactly as the single agent does. When several run at
    once only their tool activity is shown live (under their own ids), and their
    answers are combined afterwards."""
    emit = get_stream_writer()
    domain, alone = task["domain"], task["alone"]
    state = agent.AgentState(
        message=task["message"], student=task["student"], history=task["history"], entities=task["entities"], domain=domain,
        quality=task["quality"],
    )
    response = None
    for part in agent._graph.stream(state, {"recursion_limit": agent.RECURSION_LIMIT}, stream_mode="custom", version="v2"):
        event = part["data"]
        kind = event["type"]
        if kind == "done":
            response = ChatResponse.model_validate(event["payload"])
        elif alone:
            emit(event)
        elif kind in ("tool_start", "tool_done"):
            emit(agent._event(kind, **{**event["payload"], "id": f"{domain}:{event['payload']['id']}"}))
    return {"results": [(task["index"], domain, response)]}


def _combine_sources(responses: list[ChatResponse]) -> list[Source]:
    seen, combined = set(), []
    for response in responses:
        for source in response.sources or []:
            key = (source.document, source.section)
            if key not in seen:
                seen.add(key)
                combined.append(source)
    return combined


def merge_node(state: SupervisorState) -> dict:
    emit = get_stream_writer()
    ordered = sorted(state.results, key=lambda r: r[0])
    responses = [r[2] for r in ordered]
    if len(responses) == 1:
        emit(agent._event("done", **responses[0].model_dump(mode="json")))
        return {}

    sources = _combine_sources(responses)
    emit(agent._event("rag_context", sources=[s.model_dump() for s in sources]))
    answers = "\n\n".join(f"[{domain}] {response.reply}" for _, domain, response in ordered)
    try:
        reply, _ = agent._stream_completion(
            agent.get_llm_client(),
            [
                {"role": "system", "content": MERGE_PROMPT},
                {"role": "user", "content": f"The student asked: {state.message}\n\nSpecialist answers:\n{answers}"},
            ],
            emit=emit,
            tools=None,
            tier=tier_for(state.quality, agentic=False),
        )
    except AppError:
        # Better the specialists' own words than failing after the work is done.
        reply = "\n\n".join(r.reply for r in responses)
        emit(agent._event("token", text=reply))
    activity = [
        entry.model_copy(update={"id": f"{domain}:{entry.id}"})
        for _, domain, response in ordered
        for entry in (response.toolActivity or [])
    ]
    confirmation = next((r.confirmation for r in responses if r.confirmation), None)
    final = ChatResponse(reply=reply, sources=sources or None, toolActivity=activity or None, confirmation=confirmation)
    emit(agent._event("done", **final.model_dump(mode="json")))
    return {}


def build_supervisor():
    graph = StateGraph(SupervisorState)
    graph.add_node("router", router_node)
    graph.add_node("specialist", specialist_node, input_schema=dict)
    graph.add_node("merge", merge_node)
    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", fan_out, ["specialist"])
    graph.add_edge("specialist", "merge")
    graph.add_edge("merge", END)
    return graph.compile()


_supervisor = build_supervisor()


def _run_supervisor(message, history, student, entities, quality) -> Iterator[dict]:
    state = SupervisorState(message=message, student=student, history=history, entities=entities or [], quality=quality)
    for part in _supervisor.stream(state, {"recursion_limit": 25}, stream_mode="custom", version="v2"):
        yield part["data"]


def run_agent_stream(
    message: str,
    history: list[ChatHistoryItem],
    student: CurrentStudent,
    entities: list[Entity] | None = None,
    quality: str | None = None,
) -> Iterator[dict]:
    """The agent's events for a message: through the router and specialists when
    MULTI_AGENT is on, otherwise the single agent. The events are the same either way."""
    if MULTI_AGENT:
        return _run_supervisor(message, history, student, entities, quality)
    return agent.run_agent_stream(message, history, student, entities, quality)


def run_agent(
    message: str,
    history: list[ChatHistoryItem],
    student: CurrentStudent,
    entities: list[Entity] | None = None,
    quality: str | None = None,
) -> ChatResponse:
    events = list(run_agent_stream(message, history, student, entities, quality))
    return ChatResponse.model_validate(events[-1]["payload"])

import json
import threading
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from groq import APIConnectionError

from app.actions.registry import ACTIONS
from app.agent import agent, supervisor
from app.agent.domains import DOMAIN_DESCRIPTIONS, DOMAIN_TOOLS, SPECIALIST_PROMPTS, allowed_tools, schemas_for
from app.agent.supervisor import MAX_DOMAINS, MERGE_PROMPT, ROUTER_PROMPT, parse_domains
from app.agent.tool_registry import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.errors import AppError
from app.main import app
from app.models.chat import ChatHistoryItem
from fakes import _chunks
from fakes import fake_llm
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ASHA_PROFILE, sign_up


class Brain:
    """A fake model that answers according to who is asking: the router, a specialist
    (told apart by its system prompt) or the merger. It records what each was shown."""

    def __init__(self, router, specialists=None, merge=None, meet=False):
        self.router = router
        self.scripts = {d: list(r) for d, r in (specialists or {}).items()}
        self.merge = merge
        self.calls = []
        self.barrier = threading.Barrier(2, timeout=5) if meet else None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        messages = kwargs["messages"]
        first = messages[0]["content"]
        tools = sorted(t["function"]["name"] for t in kwargs.get("tools") or [])
        if first == ROUTER_PROMPT:
            self.calls.append(("router", messages, tools))
            if isinstance(self.router, Exception):
                raise self.router
            return _chunks(_completion(content=self.router))
        if first == MERGE_PROMPT:
            self.calls.append(("merge", messages, tools))
            if isinstance(self.merge, Exception):
                raise self.merge
            return _chunks(_completion(content=self.merge))
        domain = next((d for d, p in SPECIALIST_PROMPTS.items() if any(m["content"] == p for m in messages if m["role"] == "system")), None)
        self.calls.append((domain or "single", messages, tools))
        if self.barrier is not None and not any(m["role"] == "tool" for m in messages):
            self.barrier.wait()  # fails unless two specialists are asking at the same moment
        script = self.scripts.get(domain or "single", [_completion(content="single agent answer")])
        index = sum(1 for c in self.calls if c[0] == (domain or "single")) - 1
        return _chunks(script[min(index, len(script) - 1)])

    def asked(self, who):
        return [c for c in self.calls if c[0] == who]


@pytest.fixture
def multi(monkeypatch):
    monkeypatch.setattr(supervisor, "MULTI_AGENT", True)

    def install(brain, chunks=()):
        monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(brain))
        monkeypatch.setattr(agent, "retrieve", lambda message: list(chunks))
        return brain

    return install


def stream(message="hello", history=()):
    return list(supervisor.run_agent_stream(message, list(history), ASHA_PROFILE))


def kinds(events):
    return [e["type"] for e in events]


# --- the domains


def test_every_tool_and_action_belongs_to_exactly_one_specialist():
    names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    owned = [n for tools in DOMAIN_TOOLS.values() for n in tools]
    assert sorted(owned) == sorted(names), "a tool is in no domain, or in two, or does not exist"
    assert set(DOMAIN_TOOLS) == set(DOMAIN_DESCRIPTIONS) == set(SPECIALIST_PROMPTS) == {"academic", "events", "library", "grievance", "general"}
    assert set(ACTIONS) <= set(owned) and (set(TOOL_FUNCTIONS) | set(ACTIONS)) == set(owned)


def test_a_specialist_is_offered_only_its_own_tools():
    assert {s["function"]["name"] for s in schemas_for("library")} == DOMAIN_TOOLS["library"]
    assert schemas_for(None) is TOOL_SCHEMAS and allowed_tools(None) is None
    assert allowed_tools("events") == DOMAIN_TOOLS["events"]


# --- reading the router's answer


@pytest.mark.parametrize(
    "text, expected",
    [
        ('["events"]', ["events"]),
        ('["events", "academic"]', ["events", "academic"]),
        ('Sure! ["Library", " GRIEVANCE "] hope that helps', ["library", "grievance"]),
        ('```json\n["general"]\n```', ["general"]),
        ('["events", "events", "academic"]', ["events", "academic"]),
        ('["events", "astrology", 7, null]', ["events"]),
        ('["academic","events","library","general"]', ["academic", "events", "library"]),
        ('{"domains": ["events"]}', ["events"]),
        ("events", []),
        ("[]", []),
        ("[not json]", []),
        ("", []),
    ],
)
def test_the_routers_answer_is_read_defensively(text, expected):
    assert parse_domains(text) == expected and len(parse_domains(text)) <= MAX_DOMAINS


def test_the_router_is_told_the_domains_and_sees_recent_context(multi):
    brain = multi(Brain('["general"]', {"general": [_completion(content="hi")]}))
    history = [ChatHistoryItem(role="user", content="tell me about the AI Workshop"), ChatHistoryItem(role="assistant", content="It is on Monday.")]
    stream("register me for it", history)
    (_, messages, tools) = brain.asked("router")[0]
    assert all(name in messages[0]["content"] for name in DOMAIN_DESCRIPTIONS) and tools == []
    assert "AI Workshop" in messages[1]["content"] and "register me for it" in messages[1]["content"]


# --- one specialist


def test_a_single_specialist_answers_like_the_single_agent_and_sees_only_its_tools(multi):
    brain = multi(Brain('["library"]', {"library": [_completion(content="The book is on shelf CO-01.")]}))
    events = stream("where is the algorithms book?")
    assert kinds(events)[0] == "rag_context" and kinds(events)[-1] == "done"
    assert "".join(e["payload"]["text"] for e in events if e["type"] == "token") == "The book is on shelf CO-01."
    assert events[-1]["payload"]["reply"] == "The book is on shelf CO-01."
    (_, messages, tools) = brain.asked("library")[0]
    assert tools == sorted(DOMAIN_TOOLS["library"]) and any(m["content"] == SPECIALIST_PROMPTS["library"] for m in messages)
    assert [c[0] for c in brain.calls] == ["router", "library"], "no extra model call for combining one answer"


def test_a_specialist_that_uses_a_tool_reports_it_as_usual(multi):
    multi(Brain('["academic"]', {"academic": [_completion(tool_calls=[_tool_call("c1", "get_course_info", {"course_code": "ZZ999"})]), _completion(content="No such course.")]}))
    events = stream("tell me about ZZ999")
    assert kinds(events).count("tool_start") == 1 and kinds(events).count("tool_done") == 1
    assert events[-1]["payload"]["toolActivity"][0]["id"] == "c1", "ids are only prefixed when several specialists run"


def test_a_tool_outside_the_specialists_domain_is_refused(multi, db):
    brain = multi(Brain('["library"]', {"library": [_completion(tool_calls=[_tool_call("c1", "get_cgpa", {})]), _completion(content="I can't do that here.")]}))
    events = stream("what is my cgpa?")
    entry = events[-1]["payload"]["toolActivity"][0]
    assert entry["status"] == "error" and "not available" in entry["resultSummary"]
    tool_message = next(m for m in brain.asked("library")[1][1] if m["role"] == "tool")
    assert "not available" in json.loads(tool_message["content"])["error"]


def test_an_action_outside_the_specialists_domain_is_not_proposed(multi, db):
    multi(Brain('["library"]', {"library": [_completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})]), _completion(content="Not here.")]}))
    payload = stream("register me")[-1]["payload"]
    assert payload["confirmation"] is None and payload["toolActivity"][0]["status"] == "error"


def test_a_specialist_can_propose_an_action_in_its_own_domain(multi, db):
    multi(Brain('["events"]', {"events": [_completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})])]}))
    payload = stream("register me for the AI workshop")[-1]["payload"]
    assert payload["confirmation"]["title"] == "Register for AI Workshop"


# --- several specialists


COMPOUND = dict(
    router='["events", "academic"]',
    specialists={
        "events": [_completion(tool_calls=[_tool_call("c1", "search_events", {"query": "AI"})]), _completion(content="The AI Workshop is on 2026-09-01.")],
        "academic": [_completion(tool_calls=[_tool_call("c1", "get_attendance_report", {})]), _completion(content="Your attendance is fine.")],
    },
    merge="The AI Workshop is on 1 September, and your attendance is fine.",
)


def test_a_compound_question_runs_both_specialists_and_merges_their_answers(multi, db):
    brain = multi(Brain(**COMPOUND), chunks=[{"document": "events.md", "section": "Clubs", "snippet": "x"}])
    events = stream("find me an AI event and check my attendance")
    final = events[-1]["payload"]
    assert final["reply"] == COMPOUND["merge"]
    assert "".join(e["payload"]["text"] for e in events if e["type"] == "token") == COMPOUND["merge"], "only the merged answer is streamed"
    assert sorted(brain.asked("events")[0][2]) == sorted(DOMAIN_TOOLS["events"]) and len(brain.asked("merge")) == 1
    merge_input = brain.asked("merge")[0][1][1]["content"]
    assert "find me an AI event" in merge_input and "[events] The AI Workshop" in merge_input and "[academic] Your attendance" in merge_input


def test_tool_activity_from_both_specialists_is_kept_under_distinct_ids(multi, db):
    multi(Brain(**COMPOUND))
    events = stream("find me an AI event and check my attendance")
    started = [e["payload"]["id"] for e in events if e["type"] == "tool_start"]
    assert sorted(started) == ["academic:c1", "events:c1"]
    assert sorted(e["id"] for e in events[-1]["payload"]["toolActivity"]) == ["academic:c1", "events:c1"]


def test_the_specialists_really_run_at_the_same_time(multi, db):
    multi(Brain(**COMPOUND, meet=True))  # each waits for the other before answering; serial runs would time out
    assert stream("find me an AI event and check my attendance")[-1]["type"] == "done"


def test_one_sources_list_is_sent_for_a_compound_answer(multi, db):
    multi(Brain(**COMPOUND), chunks=[{"document": "events.md", "section": "Clubs", "snippet": "x"}])
    events = stream("find me an AI event and check my attendance")
    assert kinds(events).count("rag_context") == 1
    assert events[-1]["payload"]["sources"] == [{"document": "events.md", "section": "Clubs", "snippet": "x"}]


def test_a_confirmation_from_any_specialist_survives_the_merge(multi, db):
    multi(Brain(
        '["events", "academic"]',
        {"events": [_completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})])], "academic": [_completion(content="Your attendance is fine.")]},
        merge="I prepared your registration; please confirm. Your attendance is fine.",
    ))
    final = stream("register me for the AI workshop and check my attendance")[-1]["payload"]
    assert final["confirmation"]["title"] == "Register for AI Workshop"


def test_if_combining_fails_the_specialists_own_answers_are_used(multi, db):
    brain = Brain(**{**COMPOUND, "merge": APIConnectionError(request=httpx.Request("POST", "http://x"))})
    multi(brain)
    final = stream("find me an AI event and check my attendance")[-1]["payload"]
    assert "AI Workshop is on 2026-09-01" in final["reply"] and "attendance is fine" in final["reply"]


# --- when routing is unsure or fails


@pytest.mark.parametrize("router_reply", ["I think events?", "[]", '["nonsense"]'])
def test_an_unusable_route_falls_back_to_the_single_agent_with_every_tool(multi, router_reply):
    brain = multi(Brain(router_reply))
    final = stream("hello")[-1]["payload"]
    assert final["reply"] == "single agent answer"
    (_, messages, tools) = brain.asked("single")[0]
    assert tools == sorted(s["function"]["name"] for s in TOOL_SCHEMAS)
    assert not any(m["content"] in SPECIALIST_PROMPTS.values() for m in messages if m["role"] == "system")


def test_a_model_failure_while_routing_is_the_usual_error(multi):
    multi(Brain(APIConnectionError(request=httpx.Request("POST", "http://x"))))
    with pytest.raises(AppError) as info:
        stream("hello")
    assert info.value.error_code == "llm_unavailable"


def test_with_the_flag_off_there_is_no_router_at_all(monkeypatch):
    brain = Brain("unused")
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(brain))
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    assert supervisor.MULTI_AGENT is False
    assert stream("hello")[-1]["payload"]["reply"] == "single agent answer"
    assert [c[0] for c in brain.calls] == ["single"]


# --- through the chat API


def test_the_chat_endpoints_work_with_the_router_on(multi, db):
    multi(Brain('["library"]', {"library": [_completion(content="On shelf CO-01. The AI Workshop is also on.")]}))
    client = sign_up(TestClient(app))
    reply = client.post("/api/chat", json={"message": "where is the algorithms book?"}).json()
    assert reply["reply"].startswith("On shelf CO-01")
    with client.stream("POST", "/api/chat/stream", json={"message": "and now?"}) as response:
        lines = [json.loads(l[6:]) for l in response.iter_lines() if l.startswith("data: ")]
    assert lines[-1]["type"] == "done" and any(l["type"] == "token" for l in lines)

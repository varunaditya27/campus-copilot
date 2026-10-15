import json

import pytest
from fastapi.testclient import TestClient
from groq import APIConnectionError, RateLimitError
from sqlalchemy import func, select

import httpx

from app.agent import agent
from app.api import chat as chat_api
from app.core.errors import AppError
from app.db.models import ChatMessage
from app.main import app
from fakes import FailingStreamGroq, RaisingGroq
from helpers import ASHA_PROFILE, sign_up
from fakes import completion as _completion
from fakes import tool_call as _tool_call

_REQUEST = httpx.Request("POST", "http://groq.test")


def _types(events):
    return [e["type"] for e in events]


def _text(events):
    return "".join(e["payload"]["text"] for e in events if e["type"] == "token")


def _of(events, kind):
    return [e for e in events if e["type"] == kind]


def _sse_events(response):
    return [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]


# --- the event protocol


def test_plain_reply_streams_tokens_then_done(use_fakes):
    use_fakes(_completion(content="Hello there"))

    events = list(agent.run_agent_stream("hi", [], ASHA_PROFILE))

    assert _types(events) == ["rag_context", "token", "token", "done"]
    assert _text(events) == "Hello there"
    assert events[-1]["payload"]["reply"] == "Hello there"


def test_rag_context_event_carries_the_sources(use_fakes):
    chunk = {"document": "policies.md", "section": "Leave", "snippet": "Apply 3 days ahead."}
    use_fakes(_completion(content="ok"), chunks=[chunk])

    events = list(agent.run_agent_stream("leave?", [], ASHA_PROFILE))

    assert events[0] == {"type": "rag_context", "payload": {"sources": [chunk]}}


def test_tool_activity_streams_as_it_happens(use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 45, "total": 60})]),
        _completion(content="You are at 75%."),
    )

    events = list(agent.run_agent_stream("attendance?", [], ASHA_PROFILE))

    types = _types(events)
    assert types.index("tool_start") < types.index("tool_done") < types.index("token")
    assert _of(events, "tool_start")[0]["payload"] == {
        "id": "c1",
        "tool": "calculate_attendance",
        "label": "Calculating attendance",
    }
    done_tool = _of(events, "tool_done")[0]["payload"]
    assert done_tool["status"] == "done"
    assert done_tool["resultSummary"] == "75.0% attendance"
    final = events[-1]["payload"]
    assert final["reply"] == "You are at 75%."
    assert final["toolActivity"][0]["id"] == "c1"


def test_text_before_a_tool_call_is_reset(use_fakes):
    use_fakes(
        _completion(
            content="Let me check that.",
            tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})],
        ),
        _completion(content="Done."),
    )

    events = list(agent.run_agent_stream("x", [], ASHA_PROFILE))

    types = _types(events)
    assert types.index("reset") < types.index("tool_start")
    after_reset = events[types.index("reset") + 1 :]
    assert _text(after_reset) == "Done."


def test_no_reset_when_there_was_no_text_before_the_tool_call(use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})]),
        _completion(content="Done."),
    )
    assert "reset" not in _types(list(agent.run_agent_stream("x", [], ASHA_PROFILE)))


def test_register_request_streams_its_reply_and_a_confirmation(db, use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})]),
    )

    events = list(agent.run_agent_stream("register me", [], ASHA_PROFILE))

    assert "tool_start" not in _types(events)
    assert "confirm" in _text(events).lower()
    final = events[-1]["payload"]
    assert final["confirmation"]["event"]["id"] == "evt_ai_001"
    assert final["reply"] == _text(events)


def test_giving_up_after_max_rounds_streams_the_fallback(use_fakes):
    use_fakes(_completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})]))

    events = list(agent.run_agent_stream("loop", [], ASHA_PROFILE))

    assert "wasn't able to finish" in _text(events)
    assert len(_of(events, "tool_done")) == agent.MAX_TOOL_ROUNDS


# --- failures inside the generator


def test_a_failing_request_raises_an_app_error(monkeypatch):
    exc = RateLimitError("slow down", response=httpx.Response(429, request=_REQUEST), body=None)
    monkeypatch.setattr(agent, "get_groq_client", lambda: RaisingGroq(exc))
    monkeypatch.setattr(agent, "retrieve", lambda message: [])

    with pytest.raises(AppError) as info:
        list(agent.run_agent_stream("hi", [], ASHA_PROFILE))

    assert info.value.error_code == "rate_limited"


def test_a_connection_lost_mid_stream_raises_an_app_error(monkeypatch):
    monkeypatch.setattr(
        agent, "get_groq_client", lambda: FailingStreamGroq(APIConnectionError(request=_REQUEST))
    )
    monkeypatch.setattr(agent, "retrieve", lambda message: [])
    seen = []

    with pytest.raises(AppError) as info:
        for event in agent.run_agent_stream("hi", [], ASHA_PROFILE):
            seen.append(event["type"])

    assert "token" in seen
    assert info.value.error_code == "llm_unavailable"


# --- the HTTP endpoint


def _count(db, model):
    with db() as session:
        return session.scalar(select(func.count()).select_from(model))


@pytest.fixture
def browser(db):
    return sign_up(TestClient(app))


def test_stream_endpoint_sends_server_sent_events(browser, use_fakes):
    use_fakes(_completion(content="Hello there"))

    with browser.stream("POST", "/api/chat/stream", json={"message": "hi"}) as response:
        events = _sse_events(response)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert "session_id=" in response.headers["set-cookie"]
    assert _text(events) == "Hello there"
    assert events[-1]["type"] == "done"


def test_stream_endpoint_saves_the_exchange_once_it_is_done(db, browser, use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 45, "total": 60})]),
        _completion(content="You are at 75%."),
    )

    with browser.stream("POST", "/api/chat/stream", json={"message": "attendance?"}) as response:
        list(response.iter_lines())

    with db() as session:
        rows = list(session.scalars(select(ChatMessage).order_by(ChatMessage.id)))
    assert [(r.role, r.content) for r in rows] == [
        ("user", "attendance?"),
        ("assistant", "You are at 75%."),
    ]
    assert rows[1].tool_activity[0]["tool"] == "calculate_attendance"


def test_stream_endpoint_uses_the_server_side_history(browser, use_fakes):
    client = use_fakes(_completion(content="first answer"))
    with browser.stream("POST", "/api/chat/stream", json={"message": "first"}) as response:
        list(response.iter_lines())

    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy
    with browser.stream("POST", "/api/chat/stream", json={"message": "second"}) as response:
        list(response.iter_lines())

    contents = [m["content"] for m in seen["messages"] if m["role"] in ("user", "assistant")]
    assert contents == ["first", "first answer", "second"]


def test_app_error_becomes_an_error_event_and_saves_nothing(db, browser, monkeypatch):
    def failing(message, history, student):
        raise AppError(429, "rate_limited", "The AI service is busy.")
        yield

    monkeypatch.setattr(chat_api, "run_agent_stream", failing)

    with browser.stream("POST", "/api/chat/stream", json={"message": "hi"}) as response:
        events = _sse_events(response)

    assert response.status_code == 200
    assert events == [
        {"type": "error", "payload": {"error_code": "rate_limited", "message": "The AI service is busy."}}
    ]
    assert _count(db, ChatMessage) == 0


def test_unexpected_error_becomes_a_generic_error_event(db, browser, monkeypatch):
    def exploding(message, history, student):
        raise RuntimeError("secret internal detail")
        yield

    monkeypatch.setattr(chat_api, "run_agent_stream", exploding)

    with browser.stream("POST", "/api/chat/stream", json={"message": "hi"}) as response:
        body = response.read().decode()

    events = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert events[0]["payload"]["error_code"] == "internal_error"
    assert "secret internal detail" not in body
    assert _count(db, ChatMessage) == 0


def test_invalid_request_is_rejected_before_streaming(browser):
    response = browser.post("/api/chat/stream", json={"message": ""})
    assert response.status_code == 422
    assert response.json()["error_code"] == "validation_error"


def test_streaming_requires_sign_in(db):
    response = TestClient(app).post("/api/chat/stream", json={"message": "hi"})
    assert (response.status_code, response.json()["error_code"]) == (401, "not_authenticated")


def test_the_agent_is_told_who_is_signed_in(use_fakes):
    client = use_fakes(_completion(content="ok"))
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy
    list(agent.run_agent_stream("hi", [], ASHA_PROFILE))

    system_text = " ".join(m["content"] for m in seen["messages"] if m["role"] == "system")
    assert "Asha" in system_text and "1RV23IS101" in system_text

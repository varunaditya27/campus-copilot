import httpx
import pytest
from fastapi.testclient import TestClient
from groq import APIConnectionError, APIStatusError, BadRequestError, RateLimitError
from pydantic import ValidationError

from app.agent import agent
from app.main import app
from app.rag.store import KnowledgeBaseNotFound
from app.services import event_service
from helpers import ASHA_PROFILE, sign_up
from app.tools.attendance import calculate_attendance
from app.tools.events import search_events
from fakes import FakeGroq, RaisingGroq
from fakes import fake_llm
from fakes import completion as _completion
from fakes import tool_call as _tool_call

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def signed_in(db):
    return sign_up(TestClient(app, raise_server_exceptions=False))
_REQUEST = httpx.Request("POST", "http://groq.test")


def _status_error(cls, status, message="boom", body=None):
    return cls(message, response=httpx.Response(status, request=_REQUEST), body=body)


def _use_client(monkeypatch, groq_client):
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(groq_client))
    monkeypatch.setattr(agent, "retrieve", lambda message: [])


def _assert_error_shape(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error_code", "message", "detail"}
    assert body["error_code"] == code
    assert body["message"]


# 2a: malformed tool-call arguments


@pytest.mark.parametrize("raw_arguments", ["{bad", "[]", ""])
def test_malformed_tool_arguments_become_a_tool_error(monkeypatch, raw_arguments):
    call = _tool_call("c1", "calculate_attendance", {})
    call.function.arguments = raw_arguments
    client_ = FakeGroq(_completion(tool_calls=[call]), _completion(content="Sorry."))
    _use_client(monkeypatch, client_)

    response = agent.run_agent("x", [], ASHA_PROFILE)

    assert response.reply == "Sorry."
    assert response.toolActivity[0].status == "error"


def test_malformed_register_arguments_give_fallback_text(monkeypatch, db):
    call = _tool_call("c1", "register_for_event", {})
    call.function.arguments = "{bad"
    _use_client(monkeypatch, FakeGroq(_completion(tool_calls=[call])))

    response = agent.run_agent("register me", [], ASHA_PROFILE)

    assert response.confirmation is None
    assert "couldn't find that event" in response.reply


# 2b: Groq errors


def test_rate_limit_maps_to_429(monkeypatch, signed_in):
    _use_client(monkeypatch, RaisingGroq(_status_error(RateLimitError, 429)))
    _assert_error_shape(signed_in.post("/api/chat", json={"message": "hi"}), 429, "rate_limited")


@pytest.mark.parametrize(
    "exc",
    [
        _status_error(APIStatusError, 413, "Request too large"),
        _status_error(BadRequestError, 400, "Please reduce the length of the messages"),
    ],
    ids=["status-413", "bad-request-message"],
)
def test_context_too_long_maps_to_413(monkeypatch, signed_in, exc):
    _use_client(monkeypatch, RaisingGroq(exc))
    _assert_error_shape(signed_in.post("/api/chat", json={"message": "hi"}), 413, "context_too_long")


def test_connection_failure_maps_to_502(monkeypatch, signed_in):
    _use_client(monkeypatch, RaisingGroq(APIConnectionError(request=_REQUEST)))
    _assert_error_shape(signed_in.post("/api/chat", json={"message": "hi"}), 502, "llm_unavailable")


# 2c: missing knowledge base


def test_missing_knowledge_base_still_answers(monkeypatch):
    def missing(message):
        raise KnowledgeBaseNotFound("no index")

    fake = FakeGroq(_completion(content="Answer without docs."))
    seen = {}
    original = fake._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    fake.chat.completions.create = spy
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(fake))
    monkeypatch.setattr(agent, "retrieve", missing)

    response = agent.run_agent("leave policy?", [], ASHA_PROFILE)

    assert response.reply == "Answer without docs."
    assert response.sources == []
    assert any("knowledge base" in m["content"].lower() for m in seen["messages"])


def test_opening_a_missing_knowledge_base_raises_the_specific_error(chroma_client):
    from app.rag.store import ChromaStore

    with pytest.raises(KnowledgeBaseNotFound):
        ChromaStore.open(chroma_client)


# 1.4: input validation


def test_chat_rejects_oversized_message(signed_in):
    response = signed_in.post("/api/chat", json={"message": "x" * 5000})
    _assert_error_shape(response, 422, "validation_error")


def test_attendance_rejects_negative_attended():
    with pytest.raises(ValidationError):
        calculate_attendance(-1, 10)


def test_attendance_rejects_attended_above_total():
    assert "error" in calculate_attendance(11, 10)


def test_search_rejects_huge_query(db):
    with pytest.raises(ValidationError):
        search_events("x" * 500)


def test_invalid_tool_arguments_are_reported_not_raised(monkeypatch):
    call = _tool_call("c1", "calculate_attendance", {"attended": -1, "total": 10})
    _use_client(monkeypatch, FakeGroq(_completion(tool_calls=[call]), _completion(content="ok")))

    response = agent.run_agent("x", [], ASHA_PROFILE)

    assert response.toolActivity[0].status == "error"
    assert "attended" in response.toolActivity[0].resultSummary


# 2e: structured handlers


def test_not_found_uses_structured_shape(db):
    _assert_error_shape(client.get("/api/events/nope"), 404, "not_found")


def test_unexpected_exception_returns_500_without_leaking(monkeypatch, db):
    def explode():
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(event_service, "list_events", explode)
    response = client.get("/api/events")

    _assert_error_shape(response, 500, "internal_error")
    assert "secret internal detail" not in response.text

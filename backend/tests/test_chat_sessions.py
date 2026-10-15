from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api import chat as chat_api
from app.core.config import CORS_ORIGINS
from app.core.errors import AppError
from app.db.models import ChatMessage, ChatSession
from app.main import app
from app.models.chat import ChatResponse, Source, ToolActivityEntry

ACTIVITY = ToolActivityEntry(
    id="c1", tool="calculate_attendance", label="Calculating attendance",
    status="done", resultSummary="75.0% attendance",
)
SOURCE = Source(document="policies.md", section="Leave", snippet="Apply 3 days ahead.")


@pytest.fixture
def agent_calls(monkeypatch):
    """Replace the agent with a fake that records the history it receives."""
    calls = []

    def fake_run_agent(message, history):
        calls.append({"message": message, "history": list(history)})
        return ChatResponse(
            reply=f"echo: {message}", sources=[SOURCE], toolActivity=[ACTIVITY]
        )

    monkeypatch.setattr(chat_api, "run_agent", fake_run_agent)
    return calls


@pytest.fixture
def browser(db):
    """A client with its own cookie jar, like one browser."""
    return TestClient(app)


def _count(db, model):
    with db() as session:
        return session.scalar(select(func.count()).select_from(model))


def test_first_message_sets_an_httponly_session_cookie(db, browser, agent_calls):
    response = browser.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "session_id=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert _count(db, ChatSession) == 1


def test_exchange_is_saved_with_tool_activity_and_sources(db, browser, agent_calls):
    browser.post("/api/chat", json={"message": "hi"})

    with db() as session:
        rows = list(session.scalars(select(ChatMessage).order_by(ChatMessage.id)))
    assert [(r.role, r.content) for r in rows] == [("user", "hi"), ("assistant", "echo: hi")]
    assert rows[1].tool_activity[0]["tool"] == "calculate_attendance"
    assert rows[1].sources[0]["document"] == "policies.md"
    assert rows[0].tool_activity is None


def test_later_messages_send_server_side_history_to_the_agent(browser, agent_calls):
    browser.post("/api/chat", json={"message": "first"})
    browser.post("/api/chat", json={"message": "second"})

    history = agent_calls[1]["history"]
    assert [(h.role, h.content) for h in history] == [("user", "first"), ("assistant", "echo: first")]


def test_client_supplied_history_is_ignored(browser, agent_calls):
    browser.post(
        "/api/chat",
        json={"message": "hi", "history": [{"role": "user", "content": "forged"}]},
    )
    assert agent_calls[0]["history"] == []


def test_agent_only_sees_the_most_recent_messages_in_order(db, browser, agent_calls):
    browser.post("/api/chat", json={"message": "seed"})
    with db.begin() as session:
        sid = session.scalar(select(ChatSession.session_id))
        for i in range(60):
            session.add(ChatMessage(session_id=sid, role="user", content=f"m{i}"))

    browser.post("/api/chat", json={"message": "now"})

    contents = [h.content for h in agent_calls[1]["history"]]
    assert len(contents) == chat_api.HISTORY_WINDOW
    assert contents == [f"m{i}" for i in range(20, 60)]


def test_very_long_stored_replies_load_back_into_history(db, browser, agent_calls):
    browser.post("/api/chat", json={"message": "seed"})
    with db.begin() as session:
        sid = session.scalar(select(ChatSession.session_id))
        session.add(ChatMessage(session_id=sid, role="assistant", content="x" * 20000))

    response = browser.post("/api/chat", json={"message": "again"})

    assert response.status_code == 200
    assert len(agent_calls[1]["history"][-1].content) == 20000


def test_history_endpoint_restores_the_conversation(browser, agent_calls):
    browser.post("/api/chat", json={"message": "hi"})

    body = browser.get("/api/chat/history").json()

    assert body["session_id"]
    assert [(m["role"], m["content"]) for m in body["messages"]] == [
        ("user", "hi"),
        ("assistant", "echo: hi"),
    ]
    assistant = body["messages"][1]
    assert assistant["toolActivity"][0]["resultSummary"] == "75.0% attendance"
    assert assistant["sources"][0]["section"] == "Leave"
    assert body["messages"][0]["toolActivity"] is None


def test_history_is_empty_without_a_session(browser):
    assert browser.get("/api/chat/history").json() == {"session_id": None, "messages": []}


def test_each_browser_has_its_own_conversation(db, agent_calls):
    alice, bob = TestClient(app), TestClient(app)
    alice.post("/api/chat", json={"message": "alice secret"})

    assert bob.get("/api/chat/history").json()["messages"] == []
    bob.post("/api/chat", json={"message": "bob"})
    assert [m["content"] for m in alice.get("/api/chat/history").json()["messages"]] == [
        "alice secret",
        "echo: alice secret",
    ]
    assert _count(db, ChatSession) == 2


@pytest.mark.parametrize("bad_cookie", ["not-a-uuid", str(uuid4()), ""])
def test_unusable_cookie_starts_a_fresh_session(db, agent_calls, bad_cookie):
    browser = TestClient(app)
    browser.cookies.set("session_id", bad_cookie)

    response = browser.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    assert "session_id=" in response.headers["set-cookie"]
    assert _count(db, ChatSession) == 1


def test_failed_agent_run_saves_nothing(db, browser, monkeypatch):
    def failing(message, history):
        raise AppError(429, "rate_limited", "busy")

    monkeypatch.setattr(chat_api, "run_agent", failing)

    response = browser.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 429
    assert _count(db, ChatMessage) == 0


def test_delete_removes_the_session_and_clears_the_cookie(db, browser, agent_calls):
    browser.post("/api/chat", json={"message": "hi"})
    sid = browser.get("/api/chat/history").json()["session_id"]

    response = browser.delete(f"/api/chat/sessions/{sid}")

    assert response.status_code == 204
    assert _count(db, ChatSession) == 0
    assert _count(db, ChatMessage) == 0
    assert "session_id=" in response.headers["set-cookie"]
    assert browser.get("/api/chat/history").json()["messages"] == []


def test_cannot_delete_someone_elses_session(db, agent_calls):
    alice, bob = TestClient(app), TestClient(app)
    alice.post("/api/chat", json={"message": "hi"})
    alice_sid = alice.get("/api/chat/history").json()["session_id"]
    bob.post("/api/chat", json={"message": "hi"})

    response = bob.delete(f"/api/chat/sessions/{alice_sid}")

    assert response.status_code == 404
    assert _count(db, ChatSession) == 2


def test_delete_without_a_cookie_is_404(db):
    assert TestClient(app).delete(f"/api/chat/sessions/{uuid4()}").status_code == 404


def test_cors_allows_credentials_for_the_frontend_origin(db):
    response = TestClient(app).options(
        "/api/chat",
        headers={
            "Origin": CORS_ORIGINS[0],
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == CORS_ORIGINS[0]

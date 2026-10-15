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
from helpers import ASHA, RAVI, sign_up

ACTIVITY = ToolActivityEntry(
    id="c1", tool="calculate_attendance", label="Calculating attendance",
    status="done", resultSummary="75.0% attendance",
)
SOURCE = Source(document="policies.md", section="Leave", snippet="Apply 3 days ahead.")


@pytest.fixture
def agent_calls(monkeypatch):
    """Replace the agent with a fake that records what it receives."""
    calls = []

    def fake_run_agent(message, history, student):
        calls.append({"message": message, "history": list(history), "student": student})
        return ChatResponse(
            reply=f"echo: {message}", sources=[SOURCE], toolActivity=[ACTIVITY]
        )

    monkeypatch.setattr(chat_api, "run_agent", fake_run_agent)
    return calls


@pytest.fixture
def browser(db):
    """A browser where Asha is signed in."""
    return sign_up(TestClient(app), ASHA)


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


def test_the_session_belongs_to_the_signed_in_student(db, browser, agent_calls):
    browser.post("/api/chat", json={"message": "hi"})

    with db() as session:
        assert session.scalar(select(ChatSession.student_id)) == "1RV23IS101"
    assert agent_calls[0]["student"].student_id == "1RV23IS101"


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


def test_history_is_empty_before_the_first_message(browser):
    assert browser.get("/api/chat/history").json() == {"session_id": None, "messages": []}


def test_each_student_has_their_own_conversations(db, browser, agent_calls):
    ravi = sign_up(TestClient(app), RAVI)
    browser.post("/api/chat", json={"message": "asha secret"})

    assert ravi.get("/api/chat/history").json()["messages"] == []
    ravi.post("/api/chat", json={"message": "ravi"})
    assert [m["content"] for m in browser.get("/api/chat/history").json()["messages"]] == [
        "asha secret",
        "echo: asha secret",
    ]
    assert _count(db, ChatSession) == 2


def test_a_student_cannot_continue_someone_elses_session(db, browser, agent_calls):
    browser.post("/api/chat", json={"message": "asha secret"})
    asha_session = browser.get("/api/chat/history").json()["session_id"]

    ravi = sign_up(TestClient(app), RAVI)
    # A one-off Cookie header (it replaces the jar for this request, so it also
    # carries Ravi's login) keeps the client's own cookie jar clean.
    borrowed = f"access_token={ravi.cookies.get('access_token')}; session_id={asha_session}"
    ravi.post("/api/chat", json={"message": "hello"}, headers={"Cookie": borrowed})

    assert agent_calls[1]["history"] == []
    assert ravi.get("/api/chat/history").json()["session_id"] != asha_session
    assert [m["content"] for m in ravi.get("/api/chat/history").json()["messages"]] == ["hello", "echo: hello"]
    assert _count(db, ChatSession) == 2


@pytest.mark.parametrize("bad_cookie", ["not-a-uuid", str(uuid4()), ""])
def test_unusable_cookie_starts_a_fresh_session(db, browser, agent_calls, bad_cookie):
    browser.cookies.set("session_id", bad_cookie)

    response = browser.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 200
    assert "session_id=" in response.headers["set-cookie"]
    assert _count(db, ChatSession) == 1


def test_failed_agent_run_saves_nothing(db, browser, monkeypatch):
    def failing(message, history, student):
        raise AppError(429, "rate_limited", "busy")

    monkeypatch.setattr(chat_api, "run_agent", failing)

    response = browser.post("/api/chat", json={"message": "hi"})

    assert response.status_code == 429
    assert _count(db, ChatMessage) == 0


def test_sessions_are_listed_newest_first_with_a_preview(browser, agent_calls):
    browser.post("/api/chat", json={"message": "x" * 200})
    browser.cookies.clear()  # a different conversation
    sign_in = browser.post("/api/auth/login", json={"email": ASHA["email"], "password": ASHA["password"]})
    assert sign_in.status_code == 200
    browser.post("/api/chat", json={"message": "second conversation"})

    listing = browser.get("/api/chat/sessions").json()

    assert [s["preview"] for s in listing] == ["second conversation", "x" * 80]
    assert set(listing[0]) == {"session_id", "createdAt", "updatedAt", "preview"}


def test_an_empty_session_list(browser):
    assert browser.get("/api/chat/sessions").json() == []


def test_the_list_only_shows_your_own_sessions(browser, agent_calls):
    ravi = sign_up(TestClient(app), RAVI)
    ravi.post("/api/chat", json={"message": "ravi only"})
    browser.post("/api/chat", json={"message": "asha only"})

    assert [s["preview"] for s in browser.get("/api/chat/sessions").json()] == ["asha only"]


def test_delete_removes_the_session_and_clears_the_cookie(db, browser, agent_calls):
    browser.post("/api/chat", json={"message": "hi"})
    sid = browser.get("/api/chat/history").json()["session_id"]

    response = browser.delete(f"/api/chat/sessions/{sid}")

    assert response.status_code == 204
    assert _count(db, ChatSession) == 0
    assert _count(db, ChatMessage) == 0
    assert "session_id=" in response.headers["set-cookie"]
    assert browser.get("/api/chat/history").json()["messages"] == []


def test_cannot_delete_someone_elses_session(db, browser, agent_calls):
    browser.post("/api/chat", json={"message": "hi"})
    asha_sid = browser.get("/api/chat/history").json()["session_id"]
    ravi = sign_up(TestClient(app), RAVI)

    response = ravi.delete(f"/api/chat/sessions/{asha_sid}")

    assert response.status_code == 404
    assert _count(db, ChatSession) == 1
    assert _count(db, ChatMessage) == 2


def test_delete_of_an_unknown_session_is_404(browser):
    assert browser.delete(f"/api/chat/sessions/{uuid4()}").status_code == 404


@pytest.mark.parametrize(
    "method, path",
    [
        ("post", "/api/chat"),
        ("post", "/api/chat/stream"),
        ("get", "/api/chat/history"),
        ("get", "/api/chat/sessions"),
        ("delete", f"/api/chat/sessions/{uuid4()}"),
        ("post", "/api/register"),
    ],
)
def test_signing_in_is_required(db, agent_calls, method, path):
    kwargs = {"json": {"message": "hi", "event_id": "evt_ai_001"}} if method == "post" else {}

    response = getattr(TestClient(app), method)(path, **kwargs)

    assert (response.status_code, response.json()["error_code"]) == (401, "not_authenticated")
    assert agent_calls == []


def test_signing_out_ends_access(browser, agent_calls):
    browser.post("/api/auth/logout")
    assert browser.post("/api/chat", json={"message": "hi"}).status_code == 401


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

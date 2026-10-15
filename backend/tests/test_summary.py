from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import chat as chat_api
from app.core.errors import AppError
from app.db.models import ChatMessage, ChatSession
from app.main import app
from app.models.chat import ChatResponse
from app.services import summary_service
from helpers import ADMIN, ASHA, FACULTY, RAVI, sign_in_as, sign_up


@pytest.fixture
def model(monkeypatch):
    """A stand-in for the model that records how it was asked."""
    state = {"calls": [], "reply": "The student asked about the AI Workshop and registered."}

    def complete(messages):
        state["calls"].append(messages)
        reply = state["reply"]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(summary_service, "complete_text", complete)
    return state


@pytest.fixture
def asha(db, monkeypatch):
    monkeypatch.setattr(chat_api, "run_agent", lambda m, h, s, entities=None: ChatResponse(reply=f"answer to {m}"))
    return sign_up(TestClient(app), ASHA)


def session_id(client):
    return client.get("/api/chat/history").json()["session_id"]


def ask(client, text="tell me about the AI Workshop"):
    client.post("/api/chat", json={"message": text})


def summary(client, sid=None):
    return client.get(f"/api/chat/sessions/{sid or session_id(client)}/summary")


def test_a_summary_is_written_by_the_model(asha, model):
    ask(asha)
    response = summary(asha)
    assert response.status_code == 200
    assert response.json() == {
        "session_id": session_id(asha), "summary": model["reply"], "messageCount": 2, "cached": False,
    }


def test_the_model_sees_the_conversation_as_a_transcript(asha, model):
    ask(asha, "first question")
    ask(asha, "second question")
    summary(asha)

    system, user = model["calls"][0]
    assert system["role"] == "system" and "two or three short sentences" in system["content"]
    assert user["content"].splitlines() == [
        "Student: first question", "Assistant: answer to first question",
        "Student: second question", "Assistant: answer to second question",
    ]


def test_a_second_request_is_answered_without_asking_the_model(asha, model):
    ask(asha)
    summary(asha)
    again = summary(asha).json()
    assert again["cached"] is True and again["summary"] == model["reply"] and len(model["calls"]) == 1


def test_a_conversation_that_has_grown_gets_a_new_summary(asha, model):
    ask(asha)
    summary(asha)
    model["reply"] = "A longer conversation now."
    ask(asha, "one more thing")

    fresh = summary(asha).json()

    assert fresh["cached"] is False and fresh["summary"] == "A longer conversation now." and fresh["messageCount"] == 4
    assert len(model["calls"]) == 2


def test_the_summary_is_stored_with_the_conversation(asha, model, db):
    ask(asha)
    summary(asha)
    with db() as session:
        row = session.scalar(select(ChatSession))
        last = session.scalar(select(ChatMessage.id).order_by(ChatMessage.id.desc()))
    assert row.summary == model["reply"] and row.summary_through_message_id == last


def test_only_the_recent_messages_are_sent_and_long_ones_are_trimmed(asha, model, db):
    ask(asha, "x" * 2000)
    sid = UUID(session_id(asha))
    with db.begin() as session:
        for i in range(100):
            session.add(ChatMessage(session_id=sid, role="user", content=f"filler {i}"))
    summary(asha)

    lines = model["calls"][0][1]["content"].splitlines()
    assert len(lines) == summary_service.MAX_MESSAGES and lines[-1] == "Student: filler 99"
    assert all(len(line) <= summary_service.MAX_CHARS_PER_MESSAGE + 12 for line in lines)


def test_a_rambling_summary_is_cut_short(asha, model):
    ask(asha)
    model["reply"] = "word " * 500
    assert len(summary(asha).json()["summary"]) == summary_service.MAX_SUMMARY_CHARS


def test_an_empty_answer_from_the_model_is_an_error_and_not_saved(asha, model, db):
    ask(asha)
    model["reply"] = "   "
    response = summary(asha)
    assert (response.status_code, response.json()["error_code"]) == (502, "llm_unavailable")
    model["reply"] = "Now it works."
    assert summary(asha).json()["summary"] == "Now it works."


def test_model_failures_are_passed_on_as_the_usual_errors(asha, model):
    ask(asha)
    model["reply"] = AppError(429, "rate_limited", "The AI service is busy.")
    response = summary(asha)
    assert (response.status_code, response.json()["error_code"]) == (429, "rate_limited")


def test_a_conversation_with_nothing_in_it_cannot_be_summarised(asha, model, db):
    ask(asha)
    sid = session_id(asha)
    with db.begin() as session:
        for message in session.scalars(select(ChatMessage)):
            session.delete(message)
    response = summary(asha, sid)
    assert (response.status_code, response.json()["error_code"]) == (422, "empty_conversation")
    assert model["calls"] == []


def test_you_cannot_summarise_someone_elses_conversation(asha, model):
    ask(asha)
    sid = session_id(asha)
    ravi = sign_up(TestClient(app), RAVI)
    response = summary(ravi, sid)
    assert response.status_code == 404 and model["calls"] == []


def test_an_unknown_conversation_is_not_found(asha, model):
    assert summary(asha, str(uuid4())).status_code == 404


def test_signing_in_as_a_student_is_required(db, model):
    assert summary(TestClient(app), str(uuid4())).status_code == 401
    for account in (FACULTY, ADMIN):
        assert summary(sign_in_as(account), str(uuid4())).status_code == 403

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent import agent
from app.agent.prompts import build_entities_message
from app.api import chat as chat_api
from app.db.models import ConversationEntity
from app.main import app
from app.models.chat import ChatResponse
from app.models.memory import Entity
from app.services import entity_service
from fakes import completion as _completion
from helpers import ASHA, ASHA_PROFILE, RAVI, sign_up

WORKSHOP = Entity(kind="event", key="evt_ai_001", label="AI Workshop")
ML = Entity(kind="course", key="IS501", label="Machine Learning (IS501)")
SHEIKH = Entity(kind="faculty", key="Farhan Sheikh", label="Dr. Farhan Sheikh")


# --- what the model is told


def test_the_reminder_lists_each_kind_and_gives_event_ids():
    text = build_entities_message([WORKSHOP, ML, SHEIKH])
    assert "events: AI Workshop [evt_ai_001]" in text
    assert "courses: Machine Learning (IS501)" in text and "faculty: Dr. Farhan Sheikh" in text
    assert "most recent" in text and "square brackets" in text


def test_a_reminder_only_mentions_kinds_that_came_up():
    text = build_entities_message([WORKSHOP])
    assert "courses" not in text and "faculty" not in text


def captured(use_fakes):
    client = use_fakes(_completion(content="ok"))
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy
    return seen


def test_the_agent_gives_the_model_the_reminder_before_the_history(use_fakes):
    from app.models.chat import ChatHistoryItem

    seen = captured(use_fakes)
    agent.run_agent("register me for it", [ChatHistoryItem(role="user", content="earlier")], ASHA_PROFILE, [WORKSHOP])

    texts = [m["content"] for m in seen["messages"]]
    reminder = next(i for i, t in enumerate(texts) if "AI Workshop [evt_ai_001]" in t)
    assert seen["messages"][reminder]["role"] == "system"
    assert reminder < texts.index("earlier") < texts.index("register me for it")


def test_without_entities_there_is_no_reminder(use_fakes):
    seen = captured(use_fakes)
    agent.run_agent("hi", [], ASHA_PROFILE)
    assert not any("discussed" in m["content"] for m in seen["messages"] if m["role"] == "system")


# --- through the chat endpoints


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app), ASHA)


@pytest.fixture
def spy_agent(monkeypatch):
    calls = []

    def fake(message, history, student, entities=None):
        calls.append({"message": message, "entities": list(entities or [])})
        return ChatResponse(reply=f"Sure, the AI Workshop it is. ({message})")

    monkeypatch.setattr(chat_api, "run_agent", fake)
    return calls


def entity_keys(db):
    with db() as session:
        return sorted(session.scalars(select(ConversationEntity.key)))


def test_a_mention_in_one_turn_is_known_in_the_next(asha, spy_agent):
    asha.post("/api/chat", json={"message": "tell me about the AI Workshop"})
    asha.post("/api/chat", json={"message": "register me for it"})

    assert spy_agent[0]["entities"] == []
    assert [e.key for e in spy_agent[1]["entities"]] == ["evt_ai_001"]


def test_what_the_assistant_said_is_remembered_too(asha, spy_agent, db):
    asha.post("/api/chat", json={"message": "hello"})  # only the reply mentions the workshop
    assert entity_keys(db) == ["evt_ai_001"]


def test_each_conversation_has_its_own_memory(asha, spy_agent):
    asha.post("/api/chat", json={"message": "AI Workshop"})
    ravi = sign_up(TestClient(app), RAVI)
    ravi.post("/api/chat", json={"message": "hello there"})
    assert spy_agent[-1]["entities"] == []


def test_a_new_chat_starts_with_no_memory(asha, spy_agent):
    asha.post("/api/chat", json={"message": "AI Workshop"})
    sid = asha.get("/api/chat/history").json()["session_id"]
    asha.delete(f"/api/chat/sessions/{sid}")
    asha.post("/api/chat", json={"message": "again"})
    assert spy_agent[-1]["entities"] == []


def test_deleting_a_conversation_deletes_its_memory(asha, spy_agent, db):
    asha.post("/api/chat", json={"message": "AI Workshop"})
    assert entity_keys(db)
    asha.delete(f"/api/chat/sessions/{asha.get('/api/chat/history').json()['session_id']}")
    assert entity_keys(db) == []


def test_a_failure_while_remembering_does_not_fail_the_message(asha, spy_agent, monkeypatch):
    monkeypatch.setattr(entity_service, "extract", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    response = asha.post("/api/chat", json={"message": "AI Workshop"})
    assert response.status_code == 200 and response.json()["reply"].startswith("Sure")


def sse(response):
    return [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]


def test_streamed_chats_remember_and_recall_too(asha, db, monkeypatch):
    seen = []

    def fake_stream(message, history, student, entities=None):
        seen.append([e.key for e in entities or []])
        yield {"type": "done", "payload": ChatResponse(reply="The AI Workshop is on.").model_dump()}

    monkeypatch.setattr(chat_api, "run_agent_stream", fake_stream)
    for text in ("hi", "and that one?"):
        with asha.stream("POST", "/api/chat/stream", json={"message": text}) as response:
            sse(response)

    assert seen == [[], ["evt_ai_001"]]
    assert entity_keys(db) == ["evt_ai_001"]


def test_a_failed_stream_remembers_nothing(asha, db, monkeypatch):
    def failing(message, history, student, entities=None):
        raise RuntimeError("boom")
        yield

    monkeypatch.setattr(chat_api, "run_agent_stream", failing)
    with asha.stream("POST", "/api/chat/stream", json={"message": "AI Workshop"}) as response:
        sse(response)
    assert entity_keys(db) == []

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import chat as chat_api
from app.db.models import PendingAction, UsageEvent
from app.main import app
from app.models.chat import ChatResponse, Source, ToolActivityEntry
from app.services import usage_service
from helpers import ADMIN, ASHA, ASHA_PROFILE, FACULTY, RAVI, STAFF, sign_in_as, sign_up

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def reply(tools=(), sources=()):
    return ChatResponse(
        reply="ok",
        sources=[Source(document=d, section="S", snippet="x") for d in sources] or None,
        toolActivity=[ToolActivityEntry(id=f"c{i}", tool=t, label=t, status=s) for i, (t, s) in enumerate(tools)] or None,
    )


def add(db, student="1RV23IS101", session="s1", days_ago=0, terms=(), tools=(), documents=(), zero=False):
    with db.begin() as s:
        s.add(
            UsageEvent(
                created_at=NOW - timedelta(days=days_ago), student_id=student, session_id=session,
                terms=list(terms), tools=[list(t) for t in tools], documents=list(documents), zero_context=zero,
            )
        )


# --- reducing a question to its words


@pytest.mark.parametrize(
    "text, expected",
    [
        ("What are the library hours?", ["library", "hours"]),
        ("Library library LIBRARY", ["library"]),
        ("Can you tell me about the hostel mess timings", ["hostel", "mess", "timings"]),
        ("my id is 1RV23IS101 and a1 b2", []),
        ("", []),
        ("Don't forget: it's the bus-stop", ["forget", "bus-stop"]),
    ],
)
def test_a_question_is_reduced_to_its_meaningful_words(text, expected):
    assert usage_service.terms_of(text) == expected


def test_only_a_limited_number_of_words_are_kept_per_question():
    text = " ".join(f"word{chr(97 + i % 26)}{chr(97 + i // 26)}" for i in range(60))
    assert len(usage_service.terms_of(text)) == usage_service.MAX_TERMS_PER_QUESTION


# --- recording


def test_an_exchange_is_recorded_as_names_and_counts_only(db):
    usage_service.record_exchange(
        "1RV23IS101", str(uuid4()), "What are the library hours please?",
        reply(tools=[("get_cgpa", "done"), ("get_fee_dues", "error")], sources=["library.md", "library.md", "campus.md"]),
    )
    with db() as session:
        event = session.scalar(select(UsageEvent))
    assert event.terms == ["library", "hours"] and event.tools == [["get_cgpa", "done"], ["get_fee_dues", "error"]]
    assert event.documents == ["campus.md", "library.md"] and event.zero_context is False
    assert "What are" not in json.dumps([event.terms, event.tools, event.documents])


def test_a_reply_with_no_passages_is_a_zero_context_reply(db):
    usage_service.record_exchange("1RV23IS101", "s", "hello", reply())
    with db() as session:
        assert session.scalar(select(UsageEvent.zero_context)) is True


def test_recording_can_never_break_the_chat(db, monkeypatch, caplog):
    monkeypatch.setattr(usage_service, "terms_of", lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    usage_service.record_exchange("1RV23IS101", "s", "hello", reply())
    assert "Could not record usage" in caplog.text


# --- the summary


def test_daily_active_users_count_distinct_students_and_fill_empty_days(db):
    add(db, "1RV23IS101", days_ago=0)
    add(db, "1RV23IS101", days_ago=0)
    add(db, "1RV24IS219", days_ago=0)
    add(db, "1RV23IS101", days_ago=2)
    result = usage_service.summary(4, NOW)
    assert result["daily_active_users"] == [
        {"date": "2026-10-12", "users": 0, "questions": 0},
        {"date": "2026-10-13", "users": 1, "questions": 1},
        {"date": "2026-10-14", "users": 0, "questions": 0},
        {"date": "2026-10-15", "users": 2, "questions": 3},
    ]
    assert result["totals"] == {"questions": 4, "sessions": 1, "active_students": 2}


def test_events_before_the_window_are_ignored(db):
    add(db, days_ago=10)
    add(db, days_ago=1)
    assert usage_service.summary(3, NOW)["totals"]["questions"] == 1
    assert usage_service.summary(30, NOW)["totals"]["questions"] == 2


def test_messages_per_session_average_and_buckets(db):
    for _ in range(1):
        add(db, session="a")
    for _ in range(3):
        add(db, session="b")
    for _ in range(8):
        add(db, session="c")
    result = usage_service.summary(7, NOW)["messages_per_session"]
    assert result["average"] == 4.0
    assert result["buckets"] == [{"label": "1", "sessions": 1}, {"label": "2-3", "sessions": 1}, {"label": "4-6", "sessions": 0}, {"label": "7+", "sessions": 1}]


def test_tool_use_counts_calls_and_errors_most_used_first(db):
    add(db, tools=[("get_cgpa", "done"), ("get_fee_dues", "error")])
    add(db, tools=[("get_cgpa", "done"), ("get_cgpa", "error")])
    result = usage_service.summary(7, NOW)
    assert result["tool_usage"] == [{"tool": "get_cgpa", "count": 3, "errors": 1}, {"tool": "get_fee_dues", "count": 1, "errors": 1}]
    assert result["agent"]["tool_calls"] == 4 and result["agent"]["replies_with_tools"] == 2 and result["agent"]["avg_tool_calls_per_reply"] == 2.0


def test_documents_are_ranked_by_how_many_replies_cited_them(db):
    add(db, documents=["library.md", "campus.md"])
    add(db, documents=["library.md"])
    assert usage_service.summary(7, NOW)["top_documents"] == [{"document": "library.md", "count": 2}, {"document": "campus.md", "count": 1}]


def test_a_word_asked_only_once_is_never_shown(db):
    add(db, terms=["library", "unique1rv23is101"])
    add(db, terms=["library", "hostel"])
    add(db, terms=["hostel"])
    assert usage_service.summary(7, NOW)["top_terms"] == [{"term": "library", "count": 2}, {"term": "hostel", "count": 2}]


def test_zero_context_rate(db):
    add(db, zero=True)
    add(db, zero=False)
    add(db, zero=False)
    add(db, zero=False)
    rag = usage_service.summary(7, NOW)["rag"]
    assert (rag["zero_context_replies"], rag["zero_context_rate"]) == (1, 0.25)
    assert rag["average_distance"] is None and rag["cache_hit_rate"] is None and "not recorded" in rag["notes"]


def test_an_empty_database_gives_empty_but_well_formed_results(db):
    result = usage_service.summary(7, NOW)
    assert result["totals"] == {"questions": 0, "sessions": 0, "active_students": 0}
    assert result["messages_per_session"]["average"] is None and result["tool_usage"] == [] and result["top_terms"] == []
    assert result["agent"]["avg_tool_calls_per_reply"] is None and result["agent"]["actions"]["accept_rate"] is None
    assert result["rag"]["zero_context_rate"] is None and len(result["daily_active_users"]) == 7


def test_the_approval_rate_counts_those_who_decided(db):
    def action(status, expires_in=600, days_ago=0):
        with db.begin() as s:
            s.add(PendingAction(
                student_id="1RV23IS101", action="register_for_event", params={}, title="t", lines=[], status=status,
                created_at=NOW - timedelta(days=days_ago), expires_at=NOW + timedelta(seconds=expires_in),
            ))

    for status in ("confirmed", "confirmed", "failed", "cancelled"):
        action(status)
    action("expired")
    action("pending", expires_in=-5)  # never answered, and now too late
    action("pending", expires_in=300)  # still waiting
    action("confirmed", days_ago=40)  # outside the window
    actions = usage_service.summary(7, NOW)["agent"]["actions"]
    assert actions == {"proposed": 7, "confirmed": 2, "cancelled": 1, "failed": 1, "expired": 2, "waiting": 1, "accept_rate": 0.75, "decided": 4}


# --- through the chat and the endpoint


@pytest.fixture
def asha(db, monkeypatch):
    monkeypatch.setattr(chat_api, "run_agent", lambda m, h, s, entities=None: reply(tools=[("get_cgpa", "done")], sources=["library.md"]))
    return sign_up(TestClient(app))


def test_every_answered_question_is_recorded_for_the_student(asha, db):
    asha.post("/api/chat", json={"message": "what are the library hours"})
    with db() as session:
        (event,) = session.scalars(select(UsageEvent)).all()
    assert (event.student_id, event.terms, event.tools, event.documents) == ("1RV23IS101", ["library", "hours"], [["get_cgpa", "done"]], ["library.md"])


def test_streamed_questions_are_recorded_and_failed_ones_are_not(asha, db, monkeypatch):
    def fake_stream(message, history, student, entities=None):
        yield {"type": "done", "payload": reply(sources=["library.md"]).model_dump(mode="json")}

    monkeypatch.setattr(chat_api, "run_agent_stream", fake_stream)
    with asha.stream("POST", "/api/chat/stream", json={"message": "library fines"}) as response:
        list(response.iter_lines())

    def failing(message, history, student, entities=None):
        raise RuntimeError("boom")
        yield

    monkeypatch.setattr(chat_api, "run_agent_stream", failing)
    with asha.stream("POST", "/api/chat/stream", json={"message": "second"}) as response:
        list(response.iter_lines())
    with db() as session:
        assert len(session.scalars(select(UsageEvent)).all()) == 1


def test_a_failure_while_recording_does_not_fail_the_message(asha, monkeypatch):
    monkeypatch.setattr(usage_service, "terms_of", lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    assert asha.post("/api/chat", json={"message": "hello there"}).status_code == 200


def test_deleting_a_conversation_does_not_erase_the_usage_counts(asha, db):
    asha.post("/api/chat", json={"message": "library hours"})
    sid = asha.get("/api/chat/history").json()["session_id"]
    asha.delete(f"/api/chat/sessions/{sid}")
    with db() as session:
        assert len(session.scalars(select(UsageEvent)).all()) == 1


def test_the_endpoint_returns_the_summary_for_admins_only(asha, db):
    asha.post("/api/chat", json={"message": "library hours"})
    admin = sign_in_as(ADMIN)
    body = admin.get("/api/admin/analytics", params={"days": 7}).json()
    assert body["window_days"] == 7 and body["totals"]["questions"] == 1 and len(body["daily_active_users"]) == 7
    assert admin.get("/api/admin/analytics").json()["window_days"] == 30
    for params in ({"days": 0}, {"days": 366}, {"days": "x"}):
        assert admin.get("/api/admin/analytics", params=params).status_code == 422
    for client in (asha, sign_in_as(STAFF), sign_in_as(FACULTY)):
        assert client.get("/api/admin/analytics").status_code == 403
    assert TestClient(app).get("/api/admin/analytics").status_code == 401

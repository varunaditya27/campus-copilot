import logging
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import ChatSession, ConversationEntity, Course, Event
from app.models.memory import Entity
from app.services import entity_service as svc
from conftest import EVENTS

ISE = "Information Science and Engineering"
CSE = "Computer Science and Engineering"


def event(key):
    return Entity(kind="event", key=key, label=next(e["name"] for e in EVENTS if e["id"] == key))


@pytest.fixture
def session_id(db):
    sid = uuid4()
    with db.begin() as session:
        session.add(ChatSession(session_id=sid))
    return sid


def add_ml_courses(db):
    with db.begin() as session:
        session.add_all([
            Course(course_code="IS501", name="Machine Learning", credits=4, department=ISE, semester=5, kind="theory"),
            Course(course_code="CS602", name="Machine Learning", credits=3, department=CSE, semester=6, kind="theory"),
            Course(course_code="IS502", name="Physics", credits=3, department=ISE, semester=1, kind="theory"),
        ])


# --- events


def test_an_event_is_found_by_its_id(db):
    assert svc.extract("what about evt_ai_001?") == [event("evt_ai_001")]


def test_an_event_is_found_by_its_name_ignoring_case(db):
    assert svc.extract("tell me about the ai WORKSHOP please") == [event("evt_ai_001")]


def test_only_whole_words_count(db):
    assert svc.extract("the Web Nights are fun") == []


def test_unmentioned_events_are_not_found(db):
    assert svc.extract("what is the weather") == []


def test_a_shortened_event_name_is_found(db):
    with db.begin() as session:
        session.add(Event(id="evt_x", name="AI Odyssey: Building with Generative AI", category="artificial-intelligence", date="2026-09-01", time="10:00", duration_minutes=60, venue="Hall", capacity=10, registered=0, organizer="Club", description="d", tags=[]))
    assert [e.key for e in svc.extract("register me for AI Odyssey")] == ["evt_x"]


def test_two_events_can_be_found_together(db):
    assert {e.key for e in svc.extract("AI Workshop or Web Night?")} == {"evt_ai_001", "evt_web_002"}


# --- courses


def test_a_course_is_found_by_its_code(db):
    add_ml_courses(db)
    assert svc.extract("how am I doing in IS501?") == [Entity(kind="course", key="IS501", label="Machine Learning (IS501)")]


def test_unknown_or_lowercase_codes_are_ignored(db):
    add_ml_courses(db)
    assert svc.extract("ZZ999 and is501 and IS5011") == []


def test_a_course_name_means_the_students_own_departments_course(db):
    add_ml_courses(db)
    assert [e.key for e in svc.extract("my Machine Learning class", department=ISE)] == ["IS501"]
    assert [e.key for e in svc.extract("my Machine Learning class", department=CSE)] == ["CS602"]


def test_without_a_department_a_shared_course_name_is_not_guessed(db):
    add_ml_courses(db)
    assert svc.extract("Machine Learning") == []


def test_single_word_course_names_are_not_matched(db):
    add_ml_courses(db)
    assert svc.extract("Physics is hard", department=ISE) == []


def test_a_code_and_its_name_make_one_entity(db):
    add_ml_courses(db)
    assert [e.key for e in svc.extract("Machine Learning (IS501)", department=ISE)] == ["IS501"]


# --- faculty


def test_faculty_names_come_from_the_knowledge_documents():
    names = svc.faculty_names()
    assert len(names) >= 30 and names["Farhan Sheikh"] == "Dr. Farhan Sheikh" and names["Neha Kapoor"] == "Ms. Neha Kapoor"


def test_a_faculty_member_is_found_by_name(db):
    assert svc.extract("who is farhan sheikh?") == [Entity(kind="faculty", key="Farhan Sheikh", label="Dr. Farhan Sheikh")]


def test_a_surname_alone_is_too_vague(db):
    assert svc.extract("what does Sheikh teach?") == []


def test_names_with_apostrophes_work(db):
    assert [e.key for e in svc.extract("Dr. Shalini D'Souza runs the embedded lab")] == ["Shalini D'Souza"]


def test_mixed_text_finds_each_kind(db):
    add_ml_courses(db)
    found = svc.extract("Dr. Farhan Sheikh mentioned the AI Workshop and IS501")
    assert {e.kind for e in found} == {"event", "course", "faculty"}


# --- remembering


def rows(db, session_id):
    with db() as session:
        return list(session.scalars(select(ConversationEntity).where(ConversationEntity.session_id == session_id)))


def test_a_mention_is_recorded(db, session_id):
    svc.remember(session_id, [event("evt_ai_001")])
    (row,) = rows(db, session_id)
    assert (row.kind, row.key, row.label, row.mentions) == ("event", "evt_ai_001", "AI Workshop", 1)


def test_mentioning_it_again_counts_and_refreshes(db, session_id):
    svc.remember(session_id, [event("evt_ai_001")])
    svc.remember(session_id, [Entity(kind="event", key="evt_ai_001", label="AI Workshop (renamed)")])
    (row,) = rows(db, session_id)
    assert row.mentions == 2 and row.label == "AI Workshop (renamed)"


def test_the_same_thing_listed_twice_counts_once(db, session_id):
    svc.remember(session_id, [event("evt_ai_001"), event("evt_ai_001")])
    assert rows(db, session_id)[0].mentions == 1


def test_conversations_remember_separately(db, session_id):
    other = uuid4()
    with db.begin() as session:
        session.add(ChatSession(session_id=other))
    svc.remember(session_id, [event("evt_ai_001")])
    assert svc.recent(other) == [] and len(svc.recent(session_id)) == 1


def test_the_most_recent_comes_first(db, session_id):
    svc.remember(session_id, [event("evt_ai_001")])
    svc.remember(session_id, [event("evt_web_002")])
    assert [e.key for e in svc.recent(session_id)] == ["evt_web_002", "evt_ai_001"]
    svc.remember(session_id, [event("evt_ai_001")])
    assert [e.key for e in svc.recent(session_id)] == ["evt_ai_001", "evt_web_002"]


def test_only_a_few_of_each_kind_are_recalled(db, session_id):
    svc.remember(session_id, [Entity(kind="faculty", key=f"Person {i}", label=f"Dr. Person {i}") for i in range(9)])
    svc.remember(session_id, [event("evt_ai_001")])
    recalled = svc.recent(session_id)
    assert len([e for e in recalled if e.kind == "faculty"]) == svc.SHOWN_PER_KIND
    assert [e.label for e in recalled if e.kind == "faculty"][0] == "Dr. Person 8"
    assert any(e.kind == "event" for e in recalled)


def test_nothing_is_recalled_for_a_new_conversation(db, session_id):
    assert svc.recent(session_id) == []


def test_remember_exchange_uses_both_sides_of_the_exchange(db, session_id):
    svc.remember_exchange(session_id, "tell me about Web Night", "Dr. Farhan Sheikh hosts the AI Workshop.", None)
    assert {e.key for e in svc.recent(session_id)} == {"evt_web_002", "evt_ai_001", "Farhan Sheikh"}


def test_remembering_can_never_break_the_chat(db, session_id, monkeypatch, caplog):
    monkeypatch.setattr(svc, "extract", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with caplog.at_level(logging.ERROR):
        svc.remember_exchange(session_id, "x", "y", None)
    assert "Could not remember" in caplog.text


def test_the_database_allows_only_known_kinds(db, session_id):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with db.begin() as session:
            session.add(ConversationEntity(session_id=session_id, kind="planet", key="x", label="x"))

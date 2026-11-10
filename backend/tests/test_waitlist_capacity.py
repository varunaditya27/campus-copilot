from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from app.core import clock
from app.db.models import Event, EventWaitlist, Registration, Student
from app.services import action_service, push_service
from helpers import ADMIN, ASHA_PROFILE, RAVI_PROFILE, sign_in_as

RAVI, ARJUN = "1RV24IS219", "1RV22CS220"
ARJUN_PROFILE = RAVI_PROFILE.model_copy(update={"user_id": 3, "student_id": ARJUN, "name": "Arjun"})
FULL_EVENT = "evt_web_002"  # 5 of 5 seats taken in the test data


@pytest.fixture(autouse=True)
def before_the_event(db, monkeypatch):
    moment = datetime(2026, 8, 20, 9, 0)  # the test events are on 2026-09-01
    monkeypatch.setattr(clock, "now", lambda: moment)
    monkeypatch.setattr(clock, "today", lambda: moment.date())
    with db.begin() as session:
        session.add(Student(student_id=ARJUN, name="Arjun", program="CSE", year=4))


@pytest.fixture
def told(monkeypatch):
    calls = []
    monkeypatch.setattr(push_service, "notify", lambda student_id, title, body, url="/": calls.append((student_id, title, body, url)) or 1)
    return calls


def wait_for_a_seat(*profiles):
    for profile in profiles:
        confirmation = action_service.propose(profile, "join_event_waitlist", {"event_id": FULL_EVENT})
        action_service.confirm(UUID(confirmation.action_id), profile)


def change_capacity(capacity):
    body = {
        "name": "Web Night", "category": "web-development", "date": "2026-09-01", "time": "10:00", "duration_minutes": 60,
        "venue": "Hall A", "capacity": capacity, "organizer": "Test Club", "description": "Web Night description", "tags": ["react"],
    }
    return sign_in_as(ADMIN).put(f"/api/admin/events/{FULL_EVENT}", json=body)


def state(db):
    with db() as session:
        registered = session.get(Event, FULL_EVENT).registered
        seated = [r.student_id for r in session.scalars(select(Registration).where(Registration.event_id == FULL_EVENT).order_by(Registration.id))]
        waiting = [w.student_id for w in session.scalars(select(EventWaitlist).where(EventWaitlist.event_id == FULL_EVENT).order_by(EventWaitlist.id))]
    return registered, seated, waiting


def test_more_seats_register_the_first_student_waiting_and_tell_them(db, told):
    wait_for_a_seat(RAVI_PROFILE, ARJUN_PROFILE)

    response = change_capacity(6)

    assert response.status_code == 200 and response.json()["registered"] == 6
    assert state(db) == (6, [RAVI], [ARJUN])
    assert [(c[0], c[1]) for c in told] == [(RAVI, "A seat opened up")]
    assert "Web Night" in told[0][2] and told[0][3] == f"/events/{FULL_EVENT}"


def test_several_new_seats_register_the_waiting_students_in_order(db, told):
    wait_for_a_seat(RAVI_PROFILE, ARJUN_PROFILE)

    change_capacity(8)

    assert state(db) == (7, [RAVI, ARJUN], [])
    assert [c[0] for c in told] == [RAVI, ARJUN]


def test_new_seats_with_nobody_waiting_change_nothing_else(db, told):
    response = change_capacity(9)

    assert response.status_code == 200 and response.json()["registered"] == 5
    assert state(db) == (5, [], []) and told == []


def test_a_registration_made_this_way_has_a_proper_registration_id(db, told):
    wait_for_a_seat(RAVI_PROFILE)
    change_capacity(6)
    with db() as session:
        registration = session.scalar(select(Registration).where(Registration.event_id == FULL_EVENT))
    assert registration.registration_id == f"REG-{registration.id:05d}" and registration.status == "confirmed"

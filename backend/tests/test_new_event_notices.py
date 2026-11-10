import pytest

from app.db.models import PushSubscription, StudentProfile
from app.services import push_service
from helpers import ADMIN, sign_in_as

ASHA, RAVI = "1RV23IS101", "1RV24IS219"


def new_event(category="robotics"):
    return {
        "name": "Robot Rally", "category": category, "date": "2026-12-01", "time": "10:00", "duration_minutes": 90,
        "venue": "Hall B", "capacity": 40, "organizer": "Robotics Club", "description": "Build and race.", "tags": [],
    }


@pytest.fixture
def told(monkeypatch):
    calls = []
    monkeypatch.setattr(push_service, "notify", lambda student_id, title, body, url="/": calls.append((student_id, title, body, url)) or 1)
    return calls


def student(db, student_id, interests, subscribed=True):
    with db.begin() as session:
        session.add(StudentProfile(student_id=student_id, semester=5, electives=[], preferences={"interests": interests}))
        if subscribed:
            session.add(PushSubscription(student_id=student_id, endpoint=f"https://fcm.googleapis.com/fcm/send/{student_id}", p256dh="k", auth="a"))


def test_students_interested_in_the_category_are_told_about_a_new_event(db, told):
    student(db, ASHA, ["robotics", "research"])
    student(db, RAVI, ["research"])

    response = sign_in_as(ADMIN).post("/api/admin/events", json=new_event("robotics"))

    assert response.status_code == 201
    event_id = response.json()["id"]
    assert [(c[0], c[1], c[3]) for c in told] == [(ASHA, "New event: Robot Rally", f"/events/{event_id}")]
    assert "2026-12-01 at 10:00" in told[0][2] and "Hall B" in told[0][2]


def test_a_student_with_no_subscribed_browser_is_not_looked_for(db, told):
    student(db, ASHA, ["robotics"], subscribed=False)

    assert sign_in_as(ADMIN).post("/api/admin/events", json=new_event()).status_code == 201
    assert told == []


def test_nobody_is_told_when_nobody_is_interested(db, told):
    student(db, ASHA, ["research"])
    student(db, RAVI, [])

    assert sign_in_as(ADMIN).post("/api/admin/events", json=new_event()).status_code == 201
    assert told == []


def test_a_student_with_no_profile_does_not_stop_the_others_being_told(db, told):
    student(db, RAVI, ["robotics"])
    with db.begin() as session:  # subscribed, but no profile row at all
        session.add(PushSubscription(student_id=ASHA, endpoint="https://fcm.googleapis.com/fcm/send/x", p256dh="k", auth="a"))

    sign_in_as(ADMIN).post("/api/admin/events", json=new_event())

    assert [c[0] for c in told] == [RAVI]

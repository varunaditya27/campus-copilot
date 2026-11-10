from datetime import datetime, timezone

import pytest
from sqlalchemy import update

from app import worker
from app.db.models import AcademicRecord, Event, PushSubscription, Registration
from app.services import push_service, scheduled_notices
from helpers import add_academic_data

ASHA, RAVI = "1RV23IS101", "1RV24IS219"
NOW = datetime(2026, 9, 1, 8, 0)  # the test events are on 2026-09-01 at 10:00


@pytest.fixture
def told(monkeypatch):
    calls = []
    monkeypatch.setattr(push_service, "notify", lambda student_id, title, body, url="/": calls.append((student_id, title, body, url)) or 1)
    return calls


def subscribe(db, student_id):
    with db.begin() as session:
        session.add(PushSubscription(student_id=student_id, endpoint=f"https://fcm.googleapis.com/fcm/send/{student_id}", p256dh="k", auth="a"))


def register(db, student_id, event_id):
    with db.begin() as session:
        session.add(Registration(registration_id=f"REG-{student_id}-{event_id}", student_id=student_id, event_id=event_id, registered_at=datetime.now(timezone.utc)))


def event_at(db, event_id, date, time):
    with db.begin() as session:
        session.add(
            Event(id=event_id, name=f"Event {event_id}", category="research", date=date, time=time, duration_minutes=60,
                  venue="Hall A", capacity=10, registered=0, organizer="Club", description="d", tags=[])
        )


# --- event reminders


def test_a_student_is_reminded_of_each_event_starting_within_the_next_24_hours(db, told):
    subscribe(db, ASHA)
    event_at(db, "at_the_limit", "2026-09-02", "08:00")
    event_at(db, "just_after", "2026-09-02", "08:01")
    event_at(db, "starting_now", "2026-09-01", "08:00")
    event_at(db, "already_started", "2026-09-01", "07:59")
    for event_id in ("evt_ai_001", "at_the_limit", "just_after", "starting_now", "already_started"):
        register(db, ASHA, event_id)

    assert scheduled_notices.send_event_reminders(NOW) == 2

    assert [c[3] for c in told] == ["/events/evt_ai_001", "/events/at_the_limit"]
    student_id, title, body, _ = told[0]
    assert student_id == ASHA and title == "Coming up: AI Workshop" and body == "2026-09-01 at 10:00, Hall A"


def test_only_students_with_a_subscribed_browser_are_reminded(db, told):
    subscribe(db, ASHA)
    register(db, RAVI, "evt_web_002")  # Ravi has no subscribed browser

    assert scheduled_notices.send_event_reminders(NOW) == 0
    assert told == []


# --- attendance warnings


def test_a_student_below_75_percent_is_warned_with_the_courses_and_figures(db, told):
    add_academic_data(db)
    subscribe(db, ASHA)

    assert scheduled_notices.warn_low_attendance() == 1

    student_id, title, body, url = told[0]
    assert student_id == ASHA and title == "Your attendance needs attention" and url == "/"
    assert "Machine Learning 72.0%" in body and "ML Lab 50.0%" in body
    assert "Web Technologies" not in body  # 27 of 28 is fine


def test_a_student_at_or_above_75_percent_everywhere_is_left_alone(db, told):
    add_academic_data(db)
    subscribe(db, ASHA)
    with db.begin() as session:
        session.execute(update(AcademicRecord).where(AcademicRecord.student_id == ASHA, AcademicRecord.semester == 5).values(attended=AcademicRecord.total))

    assert scheduled_notices.warn_low_attendance() == 0 and told == []


def test_only_students_with_a_subscribed_browser_are_warned(db, told):
    add_academic_data(db)
    subscribe(db, RAVI)  # Ravi is at 10 of 20, but Asha, who is also low, has no browser

    assert scheduled_notices.warn_low_attendance() == 1
    assert [c[0] for c in told] == [RAVI]


def test_the_lowest_two_courses_are_named_and_the_rest_counted(db, told):
    add_academic_data(db)
    subscribe(db, ASHA)
    with db.begin() as session:
        session.execute(update(AcademicRecord).where(AcademicRecord.student_id == ASHA, AcademicRecord.semester == 5).values(attended=1))

    scheduled_notices.warn_low_attendance()
    body = told[0][2]
    assert body.index("Web Technologies 3.6%") < body.index("Machine Learning 4.0%")  # the lowest first
    assert body.endswith("and 1 more.") and "ML Lab" not in body


# --- the schedule


def test_the_jobs_are_scheduled_in_campus_time():
    conf = worker.celery_app.conf
    schedule = conf.beat_schedule

    assert conf.timezone == "Asia/Kolkata"
    daily, weekly = schedule["event-reminders"]["schedule"], schedule["attendance-warnings"]["schedule"]
    assert (daily.hour, daily.minute) == ({8}, {0})
    assert (weekly.day_of_week, weekly.hour, weekly.minute) == ({1}, {9}, {0})  # Monday 09:00
    assert all(entry["task"] in worker.celery_app.tasks for entry in schedule.values())


def test_each_task_runs_its_job(monkeypatch):
    monkeypatch.setattr(scheduled_notices, "send_event_reminders", lambda: 3)
    monkeypatch.setattr(scheduled_notices, "warn_low_attendance", lambda: 4)
    assert worker.send_event_reminders() == 3
    assert worker.warn_low_attendance() == 4

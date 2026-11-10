from datetime import datetime, timedelta

from sqlalchemy import select

from app.core import clock
from app.db import session as db_session
from app.db.models import Event, PushSubscription, Registration
from app.services import academic_service, engagement_service, push_service

REMINDER_HOURS = 24
COURSES_NAMED = 2


def _subscribed_students() -> select:
    return select(PushSubscription.student_id).distinct()


def send_event_reminders(now: datetime | None = None) -> int:
    """Remind each student of every event they registered for that starts within the next 24 hours.
    Returns how many reminders were handed to the push service."""
    now = now or clock.now()
    horizon = now + timedelta(hours=REMINDER_HOURS)
    with db_session.SessionLocal() as db:
        rows = db.execute(
            select(Registration.student_id, Event)
            .join(Event, Event.id == Registration.event_id)
            .where(
                Registration.student_id.in_(_subscribed_students()),
                Event.date.between(now.date().isoformat(), horizon.date().isoformat()),
            )
            .order_by(Event.date, Event.time, Registration.student_id)
        ).all()
    # The dates narrow it down in the database; the exact start is checked here.
    sent = 0
    for student_id, event in rows:
        if now < engagement_service.event_start(event) <= horizon:
            push_service.notify(student_id, f"Coming up: {event.name}", f"{event.date} at {event.time}, {event.venue}", f"/events/{event.id}")
            sent += 1
    return sent


def warn_low_attendance() -> int:
    """Warn each student whose attendance is below the required 75% in any course this semester,
    using the same report the assistant gives when asked. Returns how many students were warned."""
    with db_session.SessionLocal() as db:
        students = list(db.scalars(_subscribed_students()))
    warned = 0
    for student_id in students:
        low = sorted(
            (c for c in academic_service.attendance_report(student_id).get("courses", []) if c["status"] != "ok"),
            key=lambda c: c["percentage"],
        )
        if not low:
            continue
        named = ", ".join(f"{c['name']} {c['percentage']}%" for c in low[:COURSES_NAMED])
        more = f" and {len(low) - COURSES_NAMED} more" if len(low) > COURSES_NAMED else ""
        push_service.notify(student_id, "Your attendance needs attention", f"Below 75% in {named}{more}.", "/")
        warned += 1
    return warned

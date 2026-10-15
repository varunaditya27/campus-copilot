from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.core import clock
from app.db import session as db_session
from app.db.models import Event, EventDetail, EventFeedback, EventWaitlist, Registration

MAX_COMMENT_CHARS = 1000


def event_start(event: Event) -> datetime:
    return datetime.strptime(f"{event.date} {event.time}", "%Y-%m-%d %H:%M")


def has_started(event: Event) -> bool:
    return event_start(event) <= clock.now()


def _timing(event: Event) -> str:
    return "past" if has_started(event) else "upcoming"


def waitlist_position(db, event_id: str, student_id: str) -> int | None:
    entry = db.scalar(select(EventWaitlist).where(EventWaitlist.event_id == event_id, EventWaitlist.student_id == student_id))
    if entry is None:
        return None
    return db.scalar(select(func.count()).select_from(EventWaitlist).where(EventWaitlist.event_id == event_id, EventWaitlist.id <= entry.id))


def event_detail(student_id: str, event_id: str) -> dict:
    """Everything about one event, including whether the student is registered or waiting."""
    with db_session.SessionLocal() as db:
        event = db.get(Event, event_id.strip())
        if event is None:
            return {"error": f"No event found with id '{event_id.strip()}'."}
        extra = db.get(EventDetail, event.id)
        registered = db.scalar(select(Registration.registration_id).where(Registration.event_id == event.id, Registration.student_id == student_id))
        position = waitlist_position(db, event.id, student_id)
        waiting = db.scalar(select(func.count()).select_from(EventWaitlist).where(EventWaitlist.event_id == event.id))
    remaining = event.capacity - event.registered
    return {
        "event_id": event.id,
        "name": event.name,
        "category": event.category,
        "description": event.description,
        "organizer": event.organizer,
        "date": event.date,
        "time": event.time,
        "duration_minutes": event.duration_minutes,
        "venue": event.venue,
        "tags": event.tags,
        "prerequisites": extra.prerequisites if extra else None,
        "materials_needed": extra.materials if extra else None,
        "capacity": event.capacity,
        "seats_left": max(remaining, 0),
        "waitlist_length": waiting,
        "timing": _timing(event),
        "your_status": "registered" if registered else "waitlisted" if position else "not registered",
        "your_registration_id": registered,
        "your_waitlist_position": position,
    }


def my_registrations(student_id: str) -> dict:
    with db_session.SessionLocal() as db:
        rows = db.execute(
            select(Registration, Event).join(Event, Event.id == Registration.event_id).where(Registration.student_id == student_id).order_by(Event.date, Event.time)
        ).all()
        waiting = db.execute(
            select(EventWaitlist, Event).join(Event, Event.id == EventWaitlist.event_id).where(EventWaitlist.student_id == student_id).order_by(Event.date)
        ).all()
        waitlist = [
            {"event_id": e.id, "name": e.name, "date": e.date, "position": waitlist_position(db, e.id, student_id)} for _, e in waiting
        ]
    registrations = [
        {"registration_id": r.registration_id, "event_id": e.id, "name": e.name, "date": e.date, "time": e.time, "venue": e.venue, "timing": _timing(e)}
        for r, e in rows
    ]
    result = {"registrations": registrations, "waitlisted": waitlist}
    if not registrations and not waitlist:
        result["message"] = "You are not registered for any events."
    return result


# --- cancelling


def check_cancellation(student_id: str, event_id: str) -> tuple[Event, int]:
    """The event and how many students are waiting for a seat, or a ValueError."""
    with db_session.SessionLocal() as db:
        event = db.get(Event, event_id)
        if event is None:
            raise ValueError("I couldn't find that event. Look at your registrations first so I have its id.")
        registered = db.scalar(select(Registration.id).where(Registration.event_id == event_id, Registration.student_id == student_id))
        if registered is None:
            raise ValueError(f"You are not registered for {event.name}.")
        if has_started(event):
            raise ValueError(f"{event.name} has already started, so the registration can no longer be cancelled.")
        waiting = db.scalar(select(func.count()).select_from(EventWaitlist).where(EventWaitlist.event_id == event_id))
        return event, waiting


def cancel_registration(student_id: str, event_id: str) -> dict:
    """Free the student's seat. If students are waiting, the first one is registered in the same step."""
    check_cancellation(student_id, event_id)
    promoted = None
    with db_session.SessionLocal() as db:
        removed = db.execute(delete(Registration).where(Registration.event_id == event_id, Registration.student_id == student_id))
        if removed.rowcount != 1:
            db.rollback()
            raise ValueError("That registration was already cancelled.")
        db.execute(update(Event).where(Event.id == event_id, Event.registered > 0).values(registered=Event.registered - 1))
        first = db.scalar(select(EventWaitlist).where(EventWaitlist.event_id == event_id).order_by(EventWaitlist.id))
        if first is not None:
            promoted = first.student_id
            db.delete(first)
            db.execute(update(Event).where(Event.id == event_id, Event.registered < Event.capacity).values(registered=Event.registered + 1))
            registration = Registration(
                registration_id=f"pending-{first.id}-{event_id}",
                student_id=promoted,
                event_id=event_id,
                registered_at=datetime.now(timezone.utc),
                status="confirmed",
            )
            db.add(registration)
            db.flush()
            registration.registration_id = f"REG-{registration.id:05d}"
        db.commit()
    return {"promoted_student": promoted}


# --- waitlist


def check_waitlist(student_id: str, event_id: str) -> tuple[Event, int]:
    """The event and the student's would-be position, or a ValueError."""
    with db_session.SessionLocal() as db:
        event = db.get(Event, event_id)
        if event is None:
            raise ValueError("I couldn't find that event. Look it up first so I have its id.")
        if has_started(event):
            raise ValueError(f"{event.name} has already started.")
        if event.registered < event.capacity:
            raise ValueError(f"{event.name} still has seats, so you can register for it directly.")
        if db.scalar(select(Registration.id).where(Registration.event_id == event_id, Registration.student_id == student_id)):
            raise ValueError(f"You are already registered for {event.name}.")
        if waitlist_position(db, event_id, student_id):
            raise ValueError(f"You are already on the waitlist for {event.name}.")
        return event, db.scalar(select(func.count()).select_from(EventWaitlist).where(EventWaitlist.event_id == event_id)) + 1


def join_waitlist(student_id: str, event_id: str) -> int:
    check_waitlist(student_id, event_id)
    with db_session.SessionLocal() as db:
        db.add(EventWaitlist(event_id=event_id, student_id=student_id))
        try:
            db.commit()
        except IntegrityError:
            raise ValueError("You are already on the waitlist.") from None
        return waitlist_position(db, event_id, student_id)


# --- feedback


def _feedback_problem(db, student_id: str, event: Event) -> str | None:
    if not db.scalar(select(Registration.id).where(Registration.event_id == event.id, Registration.student_id == student_id)):
        return f"Feedback is for students who were registered for {event.name}."
    if not has_started(event):
        return f"{event.name} hasn't happened yet, so feedback opens once it has."
    if db.scalar(select(EventFeedback.id).where(EventFeedback.event_id == event.id, EventFeedback.student_id == student_id)):
        return f"You have already given feedback on {event.name}."
    return None


def feedback_form(student_id: str, event_id: str) -> dict:
    """The form fields, and whether this student can fill it in now."""
    with db_session.SessionLocal() as db:
        event = db.get(Event, event_id.strip())
        if event is None:
            return {"error": f"No event found with id '{event_id.strip()}'."}
        problem = _feedback_problem(db, student_id, event)
    return {
        "event_id": event.id,
        "event": event.name,
        "can_submit": problem is None,
        "reason": problem,
        "fields": [
            {"name": "rating", "type": "integer", "required": True, "min": 1, "max": 5, "meaning": "1 is poor, 5 is excellent"},
            {"name": "comments", "type": "text", "required": False, "max_length": MAX_COMMENT_CHARS},
        ],
    }


def check_feedback(student_id: str, event_id: str) -> Event:
    with db_session.SessionLocal() as db:
        event = db.get(Event, event_id)
        if event is None:
            raise ValueError("I couldn't find that event.")
        problem = _feedback_problem(db, student_id, event)
        if problem:
            raise ValueError(problem)
        return event


def submit_feedback(student_id: str, event_id: str, rating: int, comments: str | None) -> None:
    check_feedback(student_id, event_id)
    with db_session.SessionLocal() as db:
        db.add(EventFeedback(event_id=event_id, student_id=student_id, rating=rating, comments=comments))
        try:
            db.commit()
        except IntegrityError:
            raise ValueError("You have already given feedback on this event.") from None

from sqlalchemy import select

from app.db import session as db_session
from app.db.models import PushSubscription, StudentProfile
from app.services import push_service


def seat_opened(student_id: str, event) -> None:
    """Tell a student they were moved from an event's waitlist into a seat."""
    push_service.notify(
        student_id, "A seat opened up", f"You're now registered for {event.name}, {event.date} at {event.time}.", f"/events/{event.id}"
    )


def new_event(event) -> None:
    """Tell the students who are interested in the event's category that it exists. Only students with
    a browser that agreed to notifications are looked at, so the work grows with them, not the roster."""
    with db_session.SessionLocal() as db:
        subscribed = set(db.scalars(select(PushSubscription.student_id).distinct()))
        profiles = db.execute(
            select(StudentProfile.student_id, StudentProfile.preferences).where(StudentProfile.student_id.in_(subscribed))
        ).all()
    # shortcut: the interests are filtered here because JSON queries differ between SQLite and Postgres;
    # and the messages go one after another, so move this to the worker queue if many students subscribe.
    for student_id, preferences in profiles:
        if event.category in ((preferences or {}).get("interests") or []):
            push_service.notify(
                student_id, f"New event: {event.name}", f"{event.date} at {event.time}, {event.venue}", f"/events/{event.id}"
            )

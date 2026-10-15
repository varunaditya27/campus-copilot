from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError

from app.db import session as db_session
from app.db.models import Event, Registration, Student


def _full() -> dict:
    return {"success": False, "error": "This event is full"}


def _duplicate() -> dict:
    return {"success": False, "error": "Already registered for this event"}


def create_registration(student_id: str, event_id: str) -> dict:
    with db_session.SessionLocal() as session:
        event = session.get(Event, event_id)
        if event is None:
            return {"success": False, "error": f"Event '{event_id}' not found"}

        if session.get(Student, student_id) is None:
            return {"success": False, "error": f"Student '{student_id}' not found"}

        if event.registered >= event.capacity:
            return _full()

        already = session.scalar(
            select(
                exists().where(
                    Registration.student_id == student_id,
                    Registration.event_id == event_id,
                )
            )
        )
        if already:
            return _duplicate()

        # The checks above give friendly errors, but two requests can pass them
        # at the same moment. This conditional UPDATE is the real seat guard:
        # the database applies it atomically, so only one request can take the
        # last seat. The unique constraint does the same for double-booking.
        taken = session.execute(
            update(Event)
            .where(Event.id == event_id, Event.registered < Event.capacity)
            .values(registered=Event.registered + 1)
        )
        if taken.rowcount == 0:
            session.rollback()
            return _full()

        registration = Registration(
            # Placeholder: the REG-nnnnn number comes from the generated row id.
            registration_id=f"pending-{uuid4().hex}",
            student_id=student_id,
            event_id=event_id,
            registered_at=datetime.now(timezone.utc),
            status="confirmed",
        )
        session.add(registration)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            return _duplicate()

        registration.registration_id = f"REG-{registration.id:05d}"
        session.commit()
        return {"success": True, "registration_id": registration.registration_id}

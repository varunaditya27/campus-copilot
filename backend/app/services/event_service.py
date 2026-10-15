from uuid import uuid4

from sqlalchemy import delete, func, select

from app.core.errors import AppError
from app.db import session as db_session
from app.db.models import Event, EventDetail, EventFeedback, EventWaitlist, Registration, Student
from app.models.auth import CurrentUser
from app.models.events import CampusEvent, EventInput
from app.services import registration_service


def list_events() -> list[CampusEvent]:
    with db_session.SessionLocal() as session:
        rows = session.scalars(select(Event).order_by(Event.date, Event.time, Event.id))
        return [CampusEvent.model_validate(row, from_attributes=True) for row in rows]


def get_event(event_id: str) -> CampusEvent | None:
    with db_session.SessionLocal() as session:
        row = session.get(Event, event_id)
        return CampusEvent.model_validate(row, from_attributes=True) if row else None


def create_event(data: EventInput, editor: CurrentUser) -> CampusEvent:
    # A faculty member's events always belong to their own department.
    department = editor.faculty.department if editor.role == "faculty" else data.department
    with db_session.SessionLocal() as session:
        row = Event(
            id=f"evt_{uuid4().hex[:10]}",
            registered=0,
            department=department,
            **data.model_dump(exclude={"department"}),
        )
        session.add(row)
        session.commit()
        return CampusEvent.model_validate(row, from_attributes=True)


def update_event(event_id: str, data: EventInput, editor: CurrentUser) -> CampusEvent:
    with db_session.SessionLocal() as session:
        row = session.get(Event, event_id)
        if row is None:
            raise AppError(404, "not_found", f"Event '{event_id}' not found")
        if editor.role == "faculty" and row.department != editor.faculty.department:
            raise AppError(403, "forbidden", "You can only edit events from your own department.")
        if data.capacity < row.registered:
            raise AppError(
                409,
                "capacity_below_registered",
                f"{row.registered} seats are already taken, so capacity cannot go below that.",
            )

        for field, value in data.model_dump(exclude={"department"}).items():
            setattr(row, field, value)
        # Only an admin can move an event between departments.
        if editor.role == "admin" and "department" in data.model_fields_set:
            row.department = data.department
        session.commit()
        return CampusEvent.model_validate(row, from_attributes=True)


def _editable(session, event_id: str, editor: CurrentUser) -> Event:
    """The event, if this editor may manage it: an admin any, a faculty member their department's."""
    row = session.get(Event, event_id)
    if row is None:
        raise AppError(404, "not_found", f"Event '{event_id}' not found")
    if editor.role == "faculty" and row.department != editor.faculty.department:
        raise AppError(403, "forbidden", "You can only manage events from your own department.")
    return row


def delete_event(event_id: str, editor: CurrentUser, force: bool = False) -> dict:
    """Remove an event. One with registrations is refused unless force is set, which
    also removes the registrations, the waitlist and the feedback."""
    with db_session.SessionLocal() as session:
        row = _editable(session, event_id, editor)
        registrations = session.scalar(select(func.count()).select_from(Registration).where(Registration.event_id == event_id))
        if registrations and not force:
            raise AppError(
                409,
                "event_has_registrations",
                f"{registrations} students are registered. Deleting the event removes their registrations: confirm to go ahead.",
            )
        for model in (Registration, EventWaitlist, EventFeedback, EventDetail):
            session.execute(delete(model).where(model.event_id == event_id))
        session.delete(row)
        session.commit()
    return {"id": event_id, "registrations_removed": registrations}


def event_roster(event_id: str, editor: CurrentUser) -> dict:
    """An event with everyone registered and everyone waiting, for the people who manage it."""
    with db_session.SessionLocal() as session:
        row = _editable(session, event_id, editor)
        event = CampusEvent.model_validate(row, from_attributes=True)
        waiting = session.execute(
            select(EventWaitlist, Student)
            .join(Student, Student.student_id == EventWaitlist.student_id)
            .where(EventWaitlist.event_id == event_id)
            .order_by(EventWaitlist.id)
        ).all()
    return {
        "event": event,
        "registrations": registration_service.list_registrations(event_id),
        "waitlist": [
            {"position": position, "student_id": s.student_id, "student_name": s.name, "program": s.program, "year": s.year}
            for position, (_, s) in enumerate(waiting, start=1)
        ],
    }

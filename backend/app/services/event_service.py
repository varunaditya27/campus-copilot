from sqlalchemy import select

from app.db import session as db_session
from app.db.models import Event
from app.models.events import CampusEvent


def list_events() -> list[CampusEvent]:
    with db_session.SessionLocal() as session:
        rows = session.scalars(select(Event).order_by(Event.date, Event.time, Event.id))
        return [CampusEvent.model_validate(row, from_attributes=True) for row in rows]


def get_event(event_id: str) -> CampusEvent | None:
    with db_session.SessionLocal() as session:
        row = session.get(Event, event_id)
        return CampusEvent.model_validate(row, from_attributes=True) if row else None

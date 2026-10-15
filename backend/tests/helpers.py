from sqlalchemy import select

from app.db.models import Event, Registration


def all_registrations(factory):
    with factory() as session:
        return list(session.scalars(select(Registration).order_by(Registration.id)))


def event_registered(factory, event_id):
    with factory() as session:
        return session.get(Event, event_id).registered

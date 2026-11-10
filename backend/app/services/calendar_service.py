from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from icalendar import Calendar
from icalendar import Event as CalendarEvent
from sqlalchemy import select

from app.db import session as db_session
from app.db.models import Event, Registration

# Event dates and times are stored without a time zone: they are campus local time.
CAMPUS_TIMEZONE = ZoneInfo("Asia/Kolkata")


def registrations_calendar(student_id: str) -> bytes:
    """An iCalendar (.ics) file with one entry for each event the student is registered for."""
    with db_session.SessionLocal() as db:
        rows = db.execute(
            select(Registration, Event)
            .join(Event, Event.id == Registration.event_id)
            .where(Registration.student_id == student_id)
            .order_by(Event.date, Event.time)
        ).all()

    calendar = Calendar()
    calendar.add("prodid", "-//Campus Copilot//Events//EN")
    calendar.add("version", "2.0")
    stamp = datetime.now(timezone.utc)
    for registration, event in rows:
        start = datetime.fromisoformat(f"{event.date}T{event.time}").replace(tzinfo=CAMPUS_TIMEZONE)
        entry = CalendarEvent()
        # A fixed id per registration, so importing the file again updates the entry instead of duplicating it.
        entry.add("uid", f"{registration.registration_id}@campus-copilot")
        entry.add("dtstamp", stamp)
        entry.add("dtstart", start)
        entry.add("dtend", start + timedelta(minutes=event.duration_minutes))
        entry.add("summary", event.name)
        entry.add("location", event.venue)
        entry.add("description", event.description)
        calendar.add_component(entry)
    # Writes the definition of Asia/Kolkata into the file, which strict calendar apps require.
    calendar.add_missing_timezones()
    return calendar.to_ical()

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core import clock
from app.db import session as db_session
from app.db.models import RoomBooking, StudyRoom
from app.services.schedule_service import WEEKDAYS

# From the library policy: two-hour blocks, within opening hours, up to three days ahead.
ADVANCE_DAYS = 3
WEEKDAY_STARTS = ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00"]  # open 8 a.m. to 8 p.m.
SATURDAY_STARTS = ["09:00", "11:00", "13:00", "15:00"]  # open 9 a.m. to 5 p.m.


def _end(start: str) -> str:
    return f"{int(start[:2]) + 2:02d}:00"


def blocks_for(day: date) -> list[str]:
    weekday = day.weekday()
    return SATURDAY_STARTS if weekday == 5 else [] if weekday == 6 else WEEKDAY_STARTS


def resolve_date(value: str | None) -> date:
    """A bookable date, or a ValueError saying why not."""
    today = clock.today()
    word = (value or "today").strip().lower()
    try:
        day = today if word == "today" else today + timedelta(days=1) if word == "tomorrow" else date.fromisoformat(word)
    except ValueError:
        raise ValueError(f"'{value}' is not a date. Use YYYY-MM-DD, 'today' or 'tomorrow'.") from None
    if day < today:
        raise ValueError("That date has already passed.")
    if day > today + timedelta(days=ADVANCE_DAYS):
        raise ValueError(f"Discussion rooms can be booked up to {ADVANCE_DAYS} days ahead.")
    if not blocks_for(day):
        raise ValueError("The library is closed on Sundays, so rooms cannot be booked.")
    return day


def _bookable(day: date, start: str) -> bool:
    if day != clock.today():
        return True
    return datetime.combine(day, datetime.strptime(start, "%H:%M").time()) > clock.now()


def availability(day_text: str | None = None, min_capacity: int | None = None) -> dict:
    try:
        day = resolve_date(day_text)
    except ValueError as exc:
        return {"error": str(exc)}
    with db_session.SessionLocal() as db:
        rooms = db.scalars(select(StudyRoom).order_by(StudyRoom.room_id)).all()
        taken = {
            (b.room_id, b.start)
            for b in db.scalars(select(RoomBooking).where(RoomBooking.date == day.isoformat()))
        }
    listing = []
    for room in rooms:
        if min_capacity and room.capacity < min_capacity:
            continue
        free = [f"{s}-{_end(s)}" for s in blocks_for(day) if (room.room_id, s) not in taken and _bookable(day, s)]
        listing.append({"room_id": room.room_id, "name": room.name, "capacity": room.capacity, "free_slots": free})
    return {
        "date": day.isoformat(),
        "weekday": WEEKDAYS[day.weekday()],
        "rooms": listing,
        "rules": "Two-hour blocks, up to three days ahead, for groups of four to eight.",
    }


def check_booking(room_id: str, day_text: str, time_slot: str) -> tuple[StudyRoom, date, str]:
    """The room, date and start of a slot that can be booked, or a ValueError."""
    day = resolve_date(day_text)
    start = time_slot.strip().split("-")[0].strip()
    if start not in blocks_for(day):
        raise ValueError(
            "Rooms are booked in two-hour blocks starting at " + ", ".join(blocks_for(day)) + " on that day."
        )
    if not _bookable(day, start):
        raise ValueError("That time has already started.")
    with db_session.SessionLocal() as db:
        room = db.get(StudyRoom, room_id.strip().upper())
        if room is None:
            raise ValueError("I couldn't find that room. Check availability first so I have its id.")
        if db.scalar(select(RoomBooking.id).where(RoomBooking.room_id == room.room_id, RoomBooking.date == day.isoformat(), RoomBooking.start == start)):
            raise ValueError(f"{room.name} is already booked for that slot.")
    return room, day, start


def book(student_id: str, room_id: str, day_text: str, time_slot: str) -> RoomBooking:
    room, day, start = check_booking(room_id, day_text, time_slot)
    with db_session.SessionLocal() as db:
        row = RoomBooking(room_id=room.room_id, student_id=student_id, date=day.isoformat(), start=start, end=_end(start))
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            raise ValueError(f"{room.name} was just booked by someone else for that slot.") from None
        db.refresh(row)
        return row

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.core import clock
from app.db import session as db_session
from app.db.models import BusRoute, CanteenItem, LostFoundItem, MaintenanceRequest
from app.services.schedule_service import BadDay, WEEKDAYS, parse_day

# Cafeteria service hours, from the dining policy.
MEAL_HOURS = {
    "breakfast": "8:00 a.m. - 10:30 a.m.",
    "lunch": "12:00 p.m. - 3:00 p.m.",
    "evening": "4:00 p.m. - 6:00 p.m.",
    "dinner": "7:00 p.m. - 9:00 p.m. (weekdays only)",
}
MAINTENANCE_CATEGORIES = ("electrical", "plumbing", "furniture-fixtures", "cleanliness", "other")
MAX_MAINTENANCE_PER_DAY = 5
MAX_RESULTS = 10


def canteen_menu(day: str | None = None) -> dict:
    """What the Central Cafeteria serves on a day."""
    try:
        weekdays, on_date = parse_day(day, clock.today())
    except BadDay as exc:
        return {"error": str(exc)}
    if len(weekdays) != 1:
        return {"error": "Ask for one day at a time, for example 'Monday' or 'tomorrow'."}
    weekday = weekdays[0]
    with db_session.SessionLocal() as db:
        rows = db.scalars(select(CanteenItem).where(CanteenItem.weekday == weekday).order_by(CanteenItem.id)).all()
    result = {"day": WEEKDAYS[weekday], "date": on_date.isoformat() if on_date else None, "prepaid_card": "Meals are paid by loading credit onto the ID card."}
    if not rows:
        result["meals"] = []
        result["message"] = f"No cafeteria menu is published for {WEEKDAYS[weekday]}."
        return result
    meals = []
    for meal, hours in MEAL_HOURS.items():
        items = [{"item": r.item, "price": r.price, "vegetarian": r.vegetarian} for r in rows if r.meal == meal]
        if items:
            meals.append({"meal": meal, "hours": hours, "items": items})
    result["meals"] = meals
    if weekday == 5:
        result["note"] = "Dinner is served on weekdays only."
    return result


def _departures(window: dict, now: datetime) -> list[str]:
    if "departures" in window:
        return [t for t in window["departures"] + window.get("returns", []) if t >= now.strftime("%H:%M")]
    out, current = [], datetime.strptime(window["start"], "%H:%M")
    end = datetime.strptime(window["end"], "%H:%M")
    while current <= end:
        if current.strftime("%H:%M") >= now.strftime("%H:%M"):
            out.append(current.strftime("%H:%M"))
        current += timedelta(minutes=window["every_minutes"])
    return out


def bus_schedule(route: str | None = None) -> dict:
    """Shuttle routes with their stops, today's service and the next departures."""
    now = clock.now()
    weekday = now.weekday()
    with db_session.SessionLocal() as db:
        routes = db.scalars(select(BusRoute).order_by(BusRoute.route_code)).all()
    if route and route.strip():
        word = route.strip().lower().removeprefix("route").strip()
        routes = [r for r in routes if r.route_code.lower() == word or (len(word) >= 3 and word in r.name.lower())]
        if not routes:
            return {"error": f"No shuttle route matches '{route.strip()}'. The routes are A, B, C and the Saturday town shuttle."}
    listing = []
    for r in routes:
        today_windows = [w for w in r.service if weekday in w["days"]]
        upcoming = sorted({t for w in today_windows for t in _departures(w, now)})
        listing.append(
            {
                "route_code": r.route_code,
                "name": r.name,
                "stops": r.stops,
                "runs_today": bool(today_windows),
                "next_departures_from_first_stop": upcoming[:3],
                "service_today": [
                    f"{w['start']}-{w['end']} every {w['every_minutes']} min" if "every_minutes" in w
                    else f"departs {', '.join(w['departures'])}; returns {', '.join(w['returns'])}"
                    for w in today_windows
                ],
                "notes": r.notes,
            }
        )
    return {"today": WEEKDAYS[weekday], "time_now": now.strftime("%H:%M"), "routes": listing,
            "boarding": "First come, first served; no seat reservation. Free with a valid institutional ID."}


def lost_and_found(keyword: str) -> dict:
    word = keyword.strip().lower()
    if not word:
        return {"error": "Give a word to search for, such as 'umbrella' or 'keys'."}
    with db_session.SessionLocal() as db:
        rows = db.scalars(
            select(LostFoundItem)
            .where(
                LostFoundItem.status == "unclaimed",
                func.lower(LostFoundItem.description + " " + LostFoundItem.location_found).contains(word, autoescape=True),
            )
            .order_by(LostFoundItem.found_on.desc(), LostFoundItem.id.desc())
        ).all()
    items = [
        {"description": r.description, "found_at": r.location_found, "found_on": r.found_on} for r in rows[:MAX_RESULTS]
    ]
    result = {"items": items}
    if not items:
        result["message"] = f"Nothing matching '{keyword.strip()}' is listed. Items may be reported later, so check again or ask the Student Services Desk."
    else:
        result["how_to_claim"] = "Ask at the Student Services Desk, in the Main Academic Block, and bring your ID."
    return result


def add_lost_item(student_id: str, description: str, location: str) -> int:
    with db_session.SessionLocal() as db:
        row = LostFoundItem(description=description, location_found=location, found_on=clock.today().isoformat(), reported_by=student_id)
        db.add(row)
        db.commit()
        return row.id


def recent_maintenance_count(student_id: str) -> int:
    """Requests this student sent in the last 24 hours (by the real clock, as created_at is)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    with db_session.SessionLocal() as db:
        rows = db.scalars(select(MaintenanceRequest.created_at).where(MaintenanceRequest.student_id == student_id)).all()
    return sum(1 for created in rows if created.replace(tzinfo=created.tzinfo or timezone.utc) >= cutoff)


def add_maintenance_request(student_id: str, location: str, category: str, description: str) -> str:
    with db_session.SessionLocal() as db:
        row = MaintenanceRequest(student_id=student_id, location=location, category=category, description=description)
        db.add(row)
        db.commit()
        return f"MR-{row.id:05d}"

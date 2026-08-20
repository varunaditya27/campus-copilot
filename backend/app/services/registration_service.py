import json
from datetime import datetime, timezone

from app.core.config import DATA_DIR

_STUDENTS_FILE = DATA_DIR / "students.json"
_REGISTRATIONS_FILE = DATA_DIR / "registrations.json"
_EVENTS_FILE = DATA_DIR / "events.json"


def _load(path):
    return json.loads(path.read_text())


def _save(path, data) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def _student_exists(student_id: str) -> bool:
    return any(s["student_id"] == student_id for s in _load(_STUDENTS_FILE))


def _already_registered(student_id: str, event_id: str) -> bool:
    return any(
        r["student_id"] == student_id
        and r["event_id"] == event_id
        and r["status"] == "confirmed"
        for r in _load(_REGISTRATIONS_FILE)
    )


def create_registration(student_id: str, event_id: str) -> dict:
    events = _load(_EVENTS_FILE)
    event = next((e for e in events if e["id"] == event_id), None)
    if event is None:
        return {"success": False, "error": f"Event '{event_id}' not found"}

    if not _student_exists(student_id):
        return {"success": False, "error": f"Student '{student_id}' not found"}

    if event["registered"] >= event["capacity"]:
        return {"success": False, "error": "This event is full"}

    if _already_registered(student_id, event_id):
        return {"success": False, "error": "Already registered for this event"}

    registrations = _load(_REGISTRATIONS_FILE)
    registration_id = f"REG-{len(registrations) + 1:05d}"
    registrations.append(
        {
            "registration_id": registration_id,
            "student_id": student_id,
            "event_id": event_id,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "status": "confirmed",
        }
    )
    _save(_REGISTRATIONS_FILE, registrations)

    event["registered"] += 1
    _save(_EVENTS_FILE, events)

    return {"success": True, "registration_id": registration_id}

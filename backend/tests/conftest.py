import json

import pytest

from app.services import event_service, registration_service


def _event(event_id, name, category, capacity, registered, tags):
    return {
        "id": event_id,
        "name": name,
        "category": category,
        "date": "2026-09-01",
        "time": "10:00",
        "duration_minutes": 60,
        "venue": "Hall A",
        "capacity": capacity,
        "registered": registered,
        "organizer": "Test Club",
        "description": f"{name} description",
        "tags": tags,
    }


EVENTS = [
    _event("evt_ai_001", "AI Workshop", "artificial-intelligence", 10, 4, ["AI", "LLM"]),
    _event("evt_web_002", "Web Night", "web-development", 5, 5, ["react"]),
]
STUDENTS = [
    {"student_id": "S1", "name": "Asha", "program": "ISE", "year": 3},
    {"student_id": "S2", "name": "Ravi", "program": "CSE", "year": 2},
]


@pytest.fixture
def data_files(tmp_path, monkeypatch):
    """Copy a small known dataset into tmp_path and point both services at it.

    The services compute their file paths once at import time, so patching
    DATA_DIR would have no effect; the module-level path names are patched.
    """
    events_file = tmp_path / "events.json"
    students_file = tmp_path / "students.json"
    registrations_file = tmp_path / "registrations.json"
    events_file.write_text(json.dumps(EVENTS))
    students_file.write_text(json.dumps(STUDENTS))
    registrations_file.write_text("[]")

    monkeypatch.setattr(event_service, "_EVENTS_FILE", events_file)
    monkeypatch.setattr(registration_service, "_EVENTS_FILE", events_file)
    monkeypatch.setattr(registration_service, "_STUDENTS_FILE", students_file)
    monkeypatch.setattr(registration_service, "_REGISTRATIONS_FILE", registrations_file)

    return {
        "events": events_file,
        "students": students_file,
        "registrations": registrations_file,
    }

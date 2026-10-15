from app.services.registration_service import create_registration
from helpers import read_json


def test_success_writes_record_and_increments_count(data_files):
    result = create_registration("S1", "evt_ai_001")

    assert result == {"success": True, "registration_id": "REG-00001"}
    registrations = read_json(data_files["registrations"])
    assert len(registrations) == 1
    assert registrations[0]["student_id"] == "S1"
    assert registrations[0]["event_id"] == "evt_ai_001"
    assert registrations[0]["status"] == "confirmed"
    events = read_json(data_files["events"])
    assert next(e for e in events if e["id"] == "evt_ai_001")["registered"] == 5


def _assert_nothing_changed(data_files, before_events):
    assert read_json(data_files["registrations"]) == []
    assert read_json(data_files["events"]) == before_events


def test_unknown_event_is_rejected(data_files):
    before = read_json(data_files["events"])
    result = create_registration("S1", "nope")
    assert result["success"] is False
    _assert_nothing_changed(data_files, before)


def test_unknown_student_is_rejected(data_files):
    before = read_json(data_files["events"])
    result = create_registration("ghost", "evt_ai_001")
    assert result["success"] is False
    _assert_nothing_changed(data_files, before)


def test_full_event_is_rejected(data_files):
    before = read_json(data_files["events"])
    result = create_registration("S1", "evt_web_002")
    assert result == {"success": False, "error": "This event is full"}
    _assert_nothing_changed(data_files, before)


def test_duplicate_registration_is_rejected(data_files):
    create_registration("S1", "evt_ai_001")
    result = create_registration("S1", "evt_ai_001")

    assert result == {"success": False, "error": "Already registered for this event"}
    assert len(read_json(data_files["registrations"])) == 1
    events = read_json(data_files["events"])
    assert next(e for e in events if e["id"] == "evt_ai_001")["registered"] == 5

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Event, Registration
from app.services.registration_service import create_registration
from helpers import all_registrations, event_registered

ASHA = "1RV23IS101"
RAVI = "1RV24IS219"


def test_success_writes_record_and_increments_count(db):
    result = create_registration(ASHA, "evt_ai_001")

    assert result == {"success": True, "registration_id": "REG-00001"}
    registrations = all_registrations(db)
    assert len(registrations) == 1
    assert registrations[0].student_id == ASHA
    assert registrations[0].event_id == "evt_ai_001"
    assert registrations[0].status == "confirmed"
    assert event_registered(db, "evt_ai_001") == 5


def test_registration_ids_are_sequential(db):
    first = create_registration(ASHA, "evt_ai_001")
    second = create_registration(RAVI, "evt_ai_001")
    assert (first["registration_id"], second["registration_id"]) == ("REG-00001", "REG-00002")


def _assert_nothing_changed(db, event_id, registered_before):
    assert all_registrations(db) == []
    assert event_registered(db, event_id) == registered_before


def test_unknown_event_is_rejected(db):
    result = create_registration(ASHA, "nope")
    assert result["success"] is False
    assert all_registrations(db) == []


def test_unknown_student_is_rejected(db):
    result = create_registration("ghost", "evt_ai_001")
    assert result["success"] is False
    _assert_nothing_changed(db, "evt_ai_001", 4)


def test_full_event_is_rejected(db):
    result = create_registration(ASHA, "evt_web_002")
    assert result == {"success": False, "error": "This event is full"}
    _assert_nothing_changed(db, "evt_web_002", 5)


def test_duplicate_registration_is_rejected(db):
    create_registration(ASHA, "evt_ai_001")
    result = create_registration(ASHA, "evt_ai_001")

    assert result == {"success": False, "error": "Already registered for this event"}
    assert len(all_registrations(db)) == 1
    assert event_registered(db, "evt_ai_001") == 5


def test_two_people_racing_for_the_last_seat_only_one_wins(db):
    with db.begin() as session:
        event = session.get(Event, "evt_ai_001")
        event.capacity, event.registered = 5, 4

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda s: create_registration(s, "evt_ai_001"), [ASHA, RAVI]))

    assert sorted(r["success"] for r in results) == [False, True]
    assert event_registered(db, "evt_ai_001") == 5
    assert len(all_registrations(db)) == 1


def _registration(student_id=ASHA, event_id="evt_ai_001", registration_id="REG-X"):
    return Registration(
        registration_id=registration_id,
        student_id=student_id,
        event_id=event_id,
        registered_at=datetime.now(timezone.utc),
    )


def test_database_rejects_duplicate_student_event_pair(db):
    with db.begin() as session:
        session.add(_registration(registration_id="REG-A"))
    with pytest.raises(IntegrityError):
        with db.begin() as session:
            session.add(_registration(registration_id="REG-B"))


def test_database_rejects_unknown_student(db):
    with pytest.raises(IntegrityError):
        with db.begin() as session:
            session.add(_registration(student_id="9ZZ99ZZ999"))


def test_database_rejects_overbooked_event(db):
    with pytest.raises(IntegrityError):
        with db.begin() as session:
            session.get(Event, "evt_web_002").registered = 6

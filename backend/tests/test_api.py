import pytest
from fastapi.testclient import TestClient

from app.main import app
from helpers import RAVI, all_registrations, sign_up


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app))


def test_register_success(db, asha):
    response = asha.post("/api/register", json={"event_id": "evt_ai_001"})

    assert response.status_code == 200
    assert response.json() == {"success": True, "registration_id": "REG-00001", "error": None}
    assert len(all_registrations(db)) == 1


def test_registration_is_always_for_the_signed_in_student(db, asha):
    response = asha.post("/api/register", json={"event_id": "evt_ai_001", "student_id": "1RV24IS219"})

    assert response.status_code == 200
    assert [r.student_id for r in all_registrations(db)] == ["1RV23IS101"]


def test_two_students_register_independently(db, asha):
    ravi = sign_up(TestClient(app), RAVI)
    asha.post("/api/register", json={"event_id": "evt_ai_001"})

    assert ravi.post("/api/register", json={"event_id": "evt_ai_001"}).json()["success"] is True
    assert sorted(r.student_id for r in all_registrations(db)) == ["1RV23IS101", "1RV24IS219"]


def test_register_full_event_reports_error(db, asha):
    response = asha.post("/api/register", json={"event_id": "evt_web_002"})

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["error"] == "This event is full"


def test_register_missing_field_is_422(db, asha):
    assert asha.post("/api/register", json={}).status_code == 422


def test_register_rejects_an_oversized_event_id(db, asha):
    response = asha.post("/api/register", json={"event_id": "e" * 65})
    assert (response.status_code, response.json()["error_code"]) == (422, "validation_error")


def test_chat_missing_message_is_422(db, asha):
    response = asha.post("/api/chat", json={})
    assert response.status_code == 422


def test_events_are_public(db):
    response = TestClient(app).get("/api/events")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == ["evt_ai_001", "evt_web_002"]

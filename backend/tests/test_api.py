from fastapi.testclient import TestClient

from app.main import app
from helpers import all_registrations

client = TestClient(app)


def test_register_success(db):
    response = client.post("/api/register", json={"event_id": "evt_ai_001", "student_id": "1RV23IS101"})

    assert response.status_code == 200
    assert response.json() == {"success": True, "registration_id": "REG-00001", "error": None}
    assert len(all_registrations(db)) == 1


def test_register_full_event_reports_error(db):
    response = client.post("/api/register", json={"event_id": "evt_web_002", "student_id": "1RV23IS101"})

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["error"] == "This event is full"


def test_register_missing_field_is_422(db):
    response = client.post("/api/register", json={"event_id": "evt_ai_001"})
    assert response.status_code == 422


def test_chat_missing_message_is_422():
    response = client.post("/api/chat", json={"history": []})
    assert response.status_code == 422


def test_events_endpoint_lists_events(db):
    response = client.get("/api/events")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == ["evt_ai_001", "evt_web_002"]

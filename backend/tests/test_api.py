import pytest
from fastapi.testclient import TestClient

from app.main import app
from helpers import sign_up


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app))


def test_chat_missing_message_is_422(db, asha):
    response = asha.post("/api/chat", json={})
    assert response.status_code == 422


def test_events_are_public(db):
    response = TestClient(app).get("/api/events")

    assert response.status_code == 200
    assert [e["id"] for e in response.json()] == ["evt_ai_001", "evt_web_002"]


def test_the_old_direct_registration_endpoint_is_gone(asha):
    assert asha.post("/api/register", json={"event_id": "evt_ai_001"}).status_code == 404

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.core.config import CORS_ORIGINS
from app.main import app
from app.models.chat import ChatResponse
from helpers import ADMIN, ASHA, FACULTY, RAVI, add_academic_data, sign_in_as, sign_up


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app), ASHA)


def test_a_student_sees_their_own_profile(asha):
    body = asha.get("/api/students/me/profile").json()
    assert body == {
        "student_id": "1RV23IS101", "name": "Asha", "program": "ISE", "year": 3, "semester": 5,
        "section": None, "electives": [], "preferences": {"interests": []},
    }


def test_the_profile_needs_a_signed_in_student(db):
    assert TestClient(app).get("/api/students/me/profile").status_code == 401
    assert TestClient(app).put("/api/students/me/profile", json={"preferences": {"interests": []}}).status_code == 401


@pytest.mark.parametrize("account", [FACULTY, ADMIN], ids=["faculty", "admin"])
def test_other_roles_have_no_student_profile(db, account):
    client = sign_in_as(account)
    assert client.get("/api/students/me/profile").status_code == 403
    assert client.put("/api/students/me/profile", json={"preferences": {"interests": []}}).status_code == 403


def test_interests_can_be_saved_and_read_back(asha):
    saved = asha.put("/api/students/me/profile", json={"preferences": {"interests": ["robotics", "research"]}})

    assert saved.status_code == 200 and saved.json()["preferences"] == {"interests": ["robotics", "research"]}
    assert asha.get("/api/students/me/profile").json()["preferences"]["interests"] == ["robotics", "research"]


def test_saving_again_replaces_the_interests(asha):
    asha.put("/api/students/me/profile", json={"preferences": {"interests": ["robotics"]}})
    asha.put("/api/students/me/profile", json={"preferences": {"interests": []}})
    assert asha.get("/api/students/me/profile").json()["preferences"]["interests"] == []


def test_repeated_interests_are_saved_once(asha):
    body = asha.put("/api/students/me/profile", json={"preferences": {"interests": ["research", "research"]}}).json()
    assert body["preferences"]["interests"] == ["research"]


@pytest.mark.parametrize(
    "body",
    [
        {"preferences": {"interests": ["cooking"]}},
        {"preferences": {"interests": ["research"] * 7}},
        {"preferences": {"interests": "robotics"}},
        {"interests": ["robotics"]},
        {},
    ],
)
def test_bad_updates_are_refused(asha, body):
    response = asha.put("/api/students/me/profile", json=body)
    assert (response.status_code, response.json()["error_code"]) == (422, "validation_error")


def test_a_student_cannot_change_their_year_semester_or_section(asha):
    asha.put(
        "/api/students/me/profile",
        json={"preferences": {"interests": ["robotics"]}, "semester": 8, "section": "Z", "year": 1, "student_id": "1RV24IS219"},
    )
    body = asha.get("/api/students/me/profile").json()
    assert (body["semester"], body["section"], body["year"], body["student_id"]) == (5, None, 3, "1RV23IS101")


def test_each_student_has_their_own_profile(asha):
    ravi = sign_up(TestClient(app), RAVI)
    asha.put("/api/students/me/profile", json={"preferences": {"interests": ["robotics"]}})
    assert ravi.get("/api/students/me/profile").json()["preferences"]["interests"] == []


def test_a_request_from_an_unknown_site_is_refused(asha):
    response = asha.put(
        "/api/students/me/profile", json={"preferences": {"interests": ["robotics"]}}, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    assert asha.get("/api/students/me/profile").json()["preferences"]["interests"] == []


def test_the_profile_reaches_the_agent_through_the_chat_endpoint(asha, monkeypatch):
    seen = {}

    def fake_agent(message, history, student, entities=None):
        seen["student"] = student
        return ChatResponse(reply="ok")

    monkeypatch.setattr(chat_api, "run_agent", fake_agent)
    asha.put("/api/students/me/profile", json={"preferences": {"interests": ["robotics"]}})

    asha.post("/api/chat", json={"message": "hi"})

    assert seen["student"].interests == ["robotics"] and seen["student"].semester == 5


def test_electives_appear_with_their_names(asha, db):
    from app.db.models import StudentProfile

    add_academic_data(db)
    with db.begin() as session:
        session.add(StudentProfile(student_id="1RV23IS101", semester=5, section="A", electives=["A501"], preferences={}))
    body = asha.get("/api/students/me/profile").json()
    assert body["electives"] == [{"course_code": "A501", "name": "Machine Learning", "credits": 4}] and body["section"] == "A"

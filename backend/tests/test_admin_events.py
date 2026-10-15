import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Event, EventDetail, EventFeedback, EventWaitlist, Registration, Student
from app.main import app
from app.services import export_service
from helpers import ADMIN, ASHA_PROFILE, CSE, FACULTY, FACULTY_CSE, RAVI_PROFILE, STAFF, register_through_approval, sign_in_as

EVENT = {
    "name": "Robotics Night", "category": "robotics", "date": "2099-10-20", "time": "18:30",
    "duration_minutes": 90, "venue": "Lab 3", "capacity": 2, "organizer": "Robotics Club",
    "description": "Build a line follower.", "tags": ["robotics"],
}


@pytest.fixture
def admin(db):
    return sign_in_as(ADMIN)


def make_event(client, **changes):
    response = client.post("/api/admin/events", json={**EVENT, **changes})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def fill(event_id):
    register_through_approval(ASHA_PROFILE, event_id)
    register_through_approval(RAVI_PROFILE, event_id)


# --- the roster


def test_the_roster_has_the_event_the_registrations_and_the_waitlist(admin, db):
    event_id = make_event(admin)
    fill(event_id)
    with db.begin() as session:
        session.add(Student(student_id="1RV22CS220", name="Arjun", program="CSE", year=4))
        session.flush()
        session.add(EventWaitlist(event_id=event_id, student_id="1RV22CS220"))

    body = admin.get(f"/api/admin/events/{event_id}/registrations").json()

    assert (body["event"]["name"], body["event"]["registered"], body["event"]["capacity"]) == ("Robotics Night", 2, 2)
    assert [r["student_id"] for r in body["registrations"]] == ["1RV23IS101", "1RV24IS219"]
    assert body["registrations"][0]["student_name"] == "Asha"
    assert body["waitlist"] == [{"position": 1, "student_id": "1RV22CS220", "student_name": "Arjun", "program": "CSE", "year": 4}]


def test_an_unknown_event_has_no_roster(admin):
    assert admin.get("/api/admin/events/nope/registrations").status_code == 404
    assert admin.delete("/api/admin/events/nope").status_code == 404
    assert admin.post("/api/admin/events/nope/registrations/export").status_code == 404


def test_a_faculty_member_sees_only_their_own_departments_rosters(db):
    admin = sign_in_as(ADMIN)
    own = make_event(admin, department="Information Science and Engineering")
    other = make_event(admin, department=CSE)
    faculty = sign_in_as(FACULTY)
    assert faculty.get(f"/api/admin/events/{own}/registrations").status_code == 200
    for response in (
        faculty.get(f"/api/admin/events/{other}/registrations"),
        faculty.post(f"/api/admin/events/{other}/registrations/export"),
        faculty.delete(f"/api/admin/events/{other}"),
    ):
        assert response.status_code == 403


@pytest.mark.parametrize("account", [None, STAFF])
def test_staff_and_the_signed_out_cannot_use_these_endpoints(db, account):
    event_id = make_event(sign_in_as(ADMIN))
    client = sign_in_as(account) if account else TestClient(app)
    expected = 403 if account else 401
    assert client.get(f"/api/admin/events/{event_id}/registrations").status_code == expected
    assert client.delete(f"/api/admin/events/{event_id}").status_code == expected
    assert client.post(f"/api/admin/events/{event_id}/registrations/export").status_code == expected


# --- export


def test_the_export_is_a_csv_of_that_events_registrations_only(admin, db):
    event_id = make_event(admin)
    other = make_event(admin, name="Other")
    register_through_approval(ASHA_PROFILE, event_id)
    register_through_approval(RAVI_PROFILE, other)

    response = admin.post(f"/api/admin/events/{event_id}/registrations/export")

    assert response.headers["content-type"].startswith("text/csv")
    assert f"registrations-{event_id}.csv" in response.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [r["student_id"] for r in rows] == ["1RV23IS101"] and rows[0]["event_name"] == "Robotics Night"


def test_an_export_with_nobody_registered_is_just_a_header(admin):
    event_id = make_event(admin)
    assert admin.post(f"/api/admin/events/{event_id}/registrations/export").text.count("\n") == 1


@pytest.mark.parametrize("name", ["=HYPERLINK(\"http://evil\")", "+1+1", "-2", "@SUM(A1)"])
def test_cells_that_look_like_formulas_are_neutralised(admin, db, name):
    event_id = make_event(admin, name="Plain")
    register_through_approval(ASHA_PROFILE, event_id)
    with db.begin() as session:
        session.get(Student, "1RV23IS101").name = name
    rows = list(csv.DictReader(io.StringIO(admin.post(f"/api/admin/events/{event_id}/registrations/export").text)))
    assert rows[0]["student_name"] == "'" + name


def test_the_shared_csv_writer_quotes_commas_and_handles_nothing():
    text = export_service.to_csv(["a", "b"], [["x, y", None], ["=1", 3]])
    assert list(csv.reader(io.StringIO(text))) == [["a", "b"], ["x, y", ""], ["'=1", "3"]]


# --- deleting


def test_an_event_nobody_registered_for_is_deleted_outright(admin, db):
    event_id = make_event(admin)
    assert admin.delete(f"/api/admin/events/{event_id}").json() == {"id": event_id, "registrations_removed": 0}
    assert admin.get(f"/api/events/{event_id}").status_code == 404


def test_an_event_with_registrations_asks_for_confirmation_first(admin, db):
    event_id = make_event(admin)
    register_through_approval(ASHA_PROFILE, event_id)
    response = admin.delete(f"/api/admin/events/{event_id}")
    assert (response.status_code, response.json()["error_code"]) == (409, "event_has_registrations")
    assert "1 students" in response.json()["message"]
    with db() as session:
        assert session.get(Event, event_id) is not None and len(session.scalars(select(Registration)).all()) == 1


def test_forcing_removes_the_event_and_everything_attached_to_it(admin, db):
    event_id = make_event(admin)
    fill(event_id)
    with db.begin() as session:
        session.add(EventDetail(event_id=event_id, prerequisites="p", materials="m"))
        session.add(EventFeedback(event_id=event_id, student_id="1RV23IS101", rating=5))
        session.add(EventWaitlist(event_id=event_id, student_id="1RV23IS101"))
    assert admin.delete(f"/api/admin/events/{event_id}", params={"force": "true"}).json()["registrations_removed"] == 2
    with db() as session:
        for model in (Registration, EventDetail, EventFeedback, EventWaitlist):
            assert session.scalars(select(model)).all() == [], model
        assert session.get(Event, event_id) is None


def test_deleting_one_event_leaves_the_others_alone(admin, db):
    first, second = make_event(admin), make_event(admin, name="Second")
    register_through_approval(ASHA_PROFILE, second)
    admin.delete(f"/api/admin/events/{first}")
    with db() as session:
        assert session.get(Event, second) is not None and len(session.scalars(select(Registration)).all()) == 1

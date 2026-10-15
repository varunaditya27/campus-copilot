import csv
import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.db.models import Event, Registration, Student, User
from app.main import app
from app.models.auth import NewStaffAccount
from app.services import auth_service
from helpers import ADMIN, ASHA, CSE, FACULTY, FACULTY_CSE, ISE, RAVI, STAFF, sign_in_as, sign_up

EVENT = {
    "name": "Robotics Night", "category": "robotics", "date": "2026-10-20", "time": "18:30",
    "duration_minutes": 90, "venue": "Lab 3", "capacity": 30, "organizer": "Robotics Club",
    "description": "Build a line follower.", "tags": ["robotics", "workshop"],
}


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app))


# --- who has which role


def test_an_admin_signs_in_with_no_student_record(db):
    admin = sign_in_as(ADMIN)
    me = admin.get("/api/auth/me").json()
    assert (me["role"], me["student_id"], me["faculty"], me["name"]) == ("admin", None, None, "Root Admin")


def test_a_faculty_member_has_a_faculty_profile(db):
    me = sign_in_as(FACULTY).get("/api/auth/me").json()
    assert me["role"] == "faculty"
    assert me["faculty"] == {"faculty_id": "FAC-0001", "department": ISE, "office": "B-204", "office_hours": "Tue 2-4"}


def test_public_sign_up_cannot_choose_a_role(db):
    client = TestClient(app)
    response = client.post("/api/auth/register", json={**ASHA, "role": "admin"})
    assert response.status_code == 201
    assert response.json()["role"] == "student"


def test_the_database_keeps_roles_and_student_links_consistent(db):
    def add(**fields):
        with db.begin() as session:
            session.add(User(email=f"{fields['name']}@example.com", password_hash="x", **fields))

    with pytest.raises(IntegrityError):
        add(name="a", role="student", student_id=None)
    with pytest.raises(IntegrityError):
        add(name="b", role="admin", student_id="1RV23IS101")
    with pytest.raises(IntegrityError):
        add(name="c", role="superuser", student_id=None)


# --- creating staff accounts


def test_a_faculty_account_needs_a_department():
    with pytest.raises(ValidationError):
        NewStaffAccount(role="faculty", name="X", email="x@example.com", password="long enough password")


def test_staff_accounts_follow_the_password_policy():
    with pytest.raises(ValidationError):
        NewStaffAccount(role="staff", name="X", email="x@example.com", password="short")


def test_student_is_not_a_staff_role():
    with pytest.raises(ValidationError):
        NewStaffAccount(role="student", name="X", email="x@example.com", password="long enough password")


def test_a_staff_email_cannot_be_reused(db):
    sign_in_as(STAFF)
    with pytest.raises(AppError) as info:
        auth_service.create_staff_account(NewStaffAccount(**{**ADMIN, "email": "STAFF@example.com"}))
    assert info.value.error_code == "email_taken"


# --- the command-line tool


def _cli(monkeypatch, capsys, argv, passwords):
    from app import cli

    answers = iter(passwords)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(answers))
    code = cli.main(argv)
    return code, capsys.readouterr()


def test_the_cli_creates_an_admin_who_can_sign_in(db, monkeypatch, capsys):
    code, output = _cli(
        monkeypatch, capsys,
        ["create-user", "--role", "admin", "--name", "Root", "--email", "Root@Example.com"],
        ["a long enough password", "a long enough password"],
    )
    assert code == 0 and "root@example.com" in output.out
    response = TestClient(app).post("/api/auth/login", json={"email": "root@example.com", "password": "a long enough password"})
    assert response.json()["role"] == "admin"


def test_the_cli_creates_faculty_with_a_department(db, monkeypatch, capsys):
    code, _ = _cli(
        monkeypatch, capsys,
        ["create-user", "--role", "faculty", "--name", "Dr X", "--email", "x@example.com", "--department", CSE, "--office", "A1"],
        ["a long enough password"] * 2,
    )
    assert code == 0
    login = TestClient(app).post("/api/auth/login", json={"email": "x@example.com", "password": "a long enough password"})
    assert login.json()["faculty"]["department"] == CSE


@pytest.mark.parametrize(
    "argv, passwords, message",
    [
        (["--role", "admin", "--name", "R", "--email", "r@example.com"], ["a long enough password", "different"], "do not match"),
        (["--role", "admin", "--name", "R", "--email", "r@example.com"], ["short", "short"], "password"),
        (["--role", "faculty", "--name", "R", "--email", "r@example.com"], ["a long enough password"] * 2, "department"),
        (["--role", "admin", "--name", "R", "--email", "not-an-email"], ["a long enough password"] * 2, "email"),
    ],
    ids=["mismatch", "weak-password", "faculty-without-department", "bad-email"],
)
def test_the_cli_refuses_bad_input(db, monkeypatch, capsys, argv, passwords, message):
    code, output = _cli(monkeypatch, capsys, ["create-user", *argv], passwords)
    assert code == 1 and message in output.err.lower()
    with db() as session:
        assert session.scalar(select(User.id)) is None


def test_the_cli_reports_a_duplicate_email(db, monkeypatch, capsys):
    sign_in_as(STAFF)
    code, output = _cli(
        monkeypatch, capsys,
        ["create-user", "--role", "staff", "--name", "Again", "--email", STAFF["email"]],
        ["a long enough password"] * 2,
    )
    assert code == 1 and "already registered" in output.err


def test_the_cli_never_takes_a_password_as_an_argument(db, monkeypatch, capsys):
    from app import cli

    with pytest.raises(SystemExit):
        cli.main(["create-user", "--role", "admin", "--name", "R", "--email", "r@example.com", "--password", "secret"])


# --- students stay students


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/api/staff/registrations"),
        ("get", "/api/staff/registrations/export"),
        ("post", "/api/admin/events"),
        ("put", "/api/admin/events/evt_ai_001"),
    ],
)
def test_students_are_refused_staff_and_admin_endpoints(asha, method, path):
    kwargs = {"json": EVENT} if method in ("post", "put") else {}
    response = getattr(asha, method)(path, **kwargs)
    assert (response.status_code, response.json()["error_code"]) == (403, "forbidden")


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/api/staff/registrations"),
        ("get", "/api/staff/registrations/export"),
        ("post", "/api/admin/events"),
        ("put", "/api/admin/events/evt_ai_001"),
    ],
)
def test_anonymous_callers_are_asked_to_sign_in(db, method, path):
    kwargs = {"json": EVENT} if method in ("post", "put") else {}
    response = getattr(TestClient(app), method)(path, **kwargs)
    assert (response.status_code, response.json()["error_code"]) == (401, "not_authenticated")


@pytest.mark.parametrize("account", [FACULTY, STAFF, ADMIN], ids=["faculty", "staff", "admin"])
@pytest.mark.parametrize(
    "method, path",
    [
        ("post", "/api/chat"),
        ("post", "/api/chat/stream"),
        ("get", "/api/chat/history"),
        ("get", "/api/chat/sessions"),
        ("post", "/api/register"),
    ],
)
def test_student_features_are_for_students_only(db, account, method, path):
    client = sign_in_as(account)
    kwargs = {"json": {"message": "hi", "event_id": "evt_ai_001"}} if method == "post" else {}
    response = getattr(client, method)(path, **kwargs)
    assert (response.status_code, response.json()["error_code"]) == (403, "forbidden")


def test_a_student_cannot_register_other_students_or_change_events(asha, db):
    asha.post("/api/register", json={"event_id": "evt_ai_001"})
    with db() as session:
        assert session.scalar(select(Event.registered).where(Event.id == "evt_ai_001")) == 5


# --- staff: view and export registrations


def _register(db, student_id, event_id="evt_ai_001", registration_id=None):
    with db.begin() as session:
        n = session.scalar(select(Registration.id).order_by(Registration.id.desc())) or 0
        session.add(
            Registration(
                registration_id=registration_id or f"REG-{n + 1:05d}", student_id=student_id, event_id=event_id,
                registered_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            )
        )


def test_staff_see_every_registration_with_student_details(db):
    _register(db, "1RV23IS101")
    _register(db, "1RV24IS219", "evt_web_002")

    rows = sign_in_as(STAFF).get("/api/staff/registrations").json()

    assert [(r["registration_id"], r["student_name"], r["event_name"]) for r in rows] == [
        ("REG-00001", "Asha", "AI Workshop"),
        ("REG-00002", "Ravi", "Web Night"),
    ]
    assert set(rows[0]) == {
        "registration_id", "status", "registered_at", "event_id", "event_name", "event_date",
        "student_id", "student_name", "program", "year",
    }


def test_staff_can_filter_by_event(db):
    _register(db, "1RV23IS101")
    _register(db, "1RV24IS219", "evt_web_002")
    rows = sign_in_as(STAFF).get("/api/staff/registrations", params={"event_id": "evt_web_002"}).json()
    assert [r["student_id"] for r in rows] == ["1RV24IS219"]


def test_an_unknown_event_filter_is_a_404(db):
    assert sign_in_as(STAFF).get("/api/staff/registrations", params={"event_id": "nope"}).status_code == 404


def test_admins_can_do_what_staff_can(db):
    assert sign_in_as(ADMIN).get("/api/staff/registrations").status_code == 200


def test_faculty_cannot_see_registrations(db):
    assert sign_in_as(FACULTY).get("/api/staff/registrations").status_code == 403


def test_the_export_is_a_csv_download(db):
    _register(db, "1RV23IS101")

    response = sign_in_as(STAFF).get("/api/staff/registrations/export")

    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="registrations.csv"'
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "registration_id", "status", "registered_at", "event_id", "event_name", "event_date",
        "student_id", "student_name", "program", "year",
    ]
    assert rows[1][0] == "REG-00001" and rows[1][7] == "Asha" and rows[1][9] == "3"


def test_the_export_respects_the_event_filter(db):
    _register(db, "1RV23IS101")
    _register(db, "1RV24IS219", "evt_web_002")
    rows = list(csv.reader(io.StringIO(
        sign_in_as(STAFF).get("/api/staff/registrations/export", params={"event_id": "evt_ai_001"}).text
    )))
    assert len(rows) == 2 and rows[1][6] == "1RV23IS101"


@pytest.mark.parametrize("hostile", ["=HYPERLINK(\"http://evil\",\"x\")", "+1+1", "-2+3", "@SUM(A1)", "\tcmd", "＝cmd"])
def test_the_export_neutralises_spreadsheet_formulas(db, hostile):
    with db.begin() as session:
        session.add(Student(student_id="1RV25CS001", name=hostile, program="CSE", year=1))
    _register(db, "1RV25CS001")

    text = sign_in_as(STAFF).get("/api/staff/registrations/export").text

    name_cell = list(csv.reader(io.StringIO(text)))[1][7]
    assert name_cell == "'" + hostile


def test_ordinary_values_are_not_altered_by_the_export(db):
    _register(db, "1RV23IS101")
    cells = list(csv.reader(io.StringIO(sign_in_as(STAFF).get("/api/staff/registrations/export").text)))[1]
    assert not any(cell.startswith("'") for cell in cells)


# --- faculty and admins: create and edit events


def test_an_admin_creates_an_event_anyone_can_then_see(db):
    response = sign_in_as(ADMIN).post("/api/admin/events", json={**EVENT, "department": CSE})

    assert response.status_code == 201
    created = response.json()
    assert created["id"].startswith("evt_") and created["registered"] == 0 and created["department"] == CSE
    public = TestClient(app).get(f"/api/events/{created['id']}").json()
    assert public["name"] == "Robotics Night"


def test_faculty_events_always_belong_to_their_department(db):
    created = sign_in_as(FACULTY).post("/api/admin/events", json={**EVENT, "department": CSE}).json()
    assert created["department"] == ISE


def test_faculty_can_edit_their_departments_events(db):
    faculty = sign_in_as(FACULTY)
    event_id = faculty.post("/api/admin/events", json=EVENT).json()["id"]

    response = faculty.put(f"/api/admin/events/{event_id}", json={**EVENT, "venue": "Lab 9", "department": CSE})

    assert response.status_code == 200
    assert response.json()["venue"] == "Lab 9"
    assert response.json()["department"] == ISE  # faculty cannot move an event


def test_faculty_cannot_edit_another_departments_event(db):
    event_id = sign_in_as(FACULTY_CSE).post("/api/admin/events", json=EVENT).json()["id"]
    response = sign_in_as(FACULTY).put(f"/api/admin/events/{event_id}", json={**EVENT, "name": "Hijacked"})
    assert (response.status_code, response.json()["error_code"]) == (403, "forbidden")
    assert TestClient(app).get(f"/api/events/{event_id}").json()["name"] == "Robotics Night"


def test_faculty_cannot_edit_events_that_have_no_department(db):
    assert sign_in_as(FACULTY).put("/api/admin/events/evt_ai_001", json=EVENT).status_code == 403


def test_admins_can_edit_any_event_and_move_it_between_departments(db):
    admin = sign_in_as(ADMIN)

    response = admin.put("/api/admin/events/evt_ai_001", json={**EVENT, "department": ISE})

    assert response.status_code == 200 and response.json()["department"] == ISE
    kept = admin.put("/api/admin/events/evt_ai_001", json=EVENT).json()
    assert kept["department"] == ISE  # not mentioned, so unchanged


def test_editing_never_changes_the_seat_count_or_id(db):
    updated = sign_in_as(ADMIN).put("/api/admin/events/evt_ai_001", json={**EVENT, "capacity": 50}).json()
    assert (updated["id"], updated["registered"], updated["capacity"]) == ("evt_ai_001", 4, 50)


def test_capacity_cannot_drop_below_the_seats_already_taken(db):
    response = sign_in_as(ADMIN).put("/api/admin/events/evt_ai_001", json={**EVENT, "capacity": 3})
    assert (response.status_code, response.json()["error_code"]) == (409, "capacity_below_registered")
    with db() as session:
        assert session.scalar(select(Event.capacity).where(Event.id == "evt_ai_001")) == 10


def test_editing_an_unknown_event_is_a_404(db):
    assert sign_in_as(ADMIN).put("/api/admin/events/nope", json=EVENT).status_code == 404


@pytest.mark.parametrize(
    "overrides",
    [
        {"date": "2026-13-45"}, {"date": "20261020"}, {"date": "tomorrow"}, {"time": "25:00"}, {"time": "6pm"},
        {"category": "cooking"}, {"capacity": 0}, {"duration_minutes": 0}, {"name": " "},
        {"tags": ["x"] * 21}, {"description": ""},
    ],
)
def test_event_input_is_validated(db, overrides):
    response = sign_in_as(ADMIN).post("/api/admin/events", json={**EVENT, **overrides})
    assert (response.status_code, response.json()["error_code"]) == (422, "validation_error")


def test_created_events_can_be_registered_for(db):
    event_id = sign_in_as(ADMIN).post("/api/admin/events", json=EVENT).json()["id"]
    student = sign_up(TestClient(app), RAVI)
    assert student.post("/api/register", json={"event_id": event_id}).json()["success"] is True
    assert TestClient(app).get(f"/api/events/{event_id}").json()["registered"] == 1


def test_a_signed_out_admin_loses_access(db):
    admin = sign_in_as(ADMIN)
    admin.post("/api/auth/logout")
    assert admin.post("/api/admin/events", json=EVENT).status_code == 401

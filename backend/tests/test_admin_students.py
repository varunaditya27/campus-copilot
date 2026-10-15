import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Student
from app.main import app
from helpers import ADMIN, FACULTY, STAFF, add_academic_data, sign_in_as, sign_up


@pytest.fixture
def admin(db):
    return sign_in_as(ADMIN)


@pytest.fixture
def roster(db):
    with db.begin() as session:
        session.add_all(
            Student(student_id=f"1RV2{i % 5}CS{100 + i}", name=f"Student {chr(65 + i)}", program="CSE" if i % 2 else "ISE", year=1 + i % 4)
            for i in range(30)
        )


def csv_file(text, name="students.csv"):
    return {"file": (name, io.BytesIO(text.encode("utf-8")), "text/csv")}


GOOD = "student_id,name,program,year\n1RV25CS501,Meera Nair,CSE,1\n1RV25CS502,Karan Shah,CSE,1\n"


# --- who may use it


@pytest.mark.parametrize("account", [None, STAFF, FACULTY])
def test_only_admins_manage_students(db, account):
    client = sign_in_as(account) if account else TestClient(app)
    expected = 403 if account else 401
    assert client.get("/api/admin/students").status_code == expected
    assert client.get("/api/admin/students/1RV23IS101").status_code == expected
    assert client.post("/api/admin/students/import", files=csv_file(GOOD)).status_code == expected


def test_a_student_cannot_reach_them(db):
    assert sign_up(TestClient(app)).get("/api/admin/students").status_code == 403


# --- list and search


def test_the_list_is_paged_and_sorted_with_a_total(admin, roster):
    first = admin.get("/api/admin/students", params={"page_size": 10}).json()
    assert (first["total"], first["page"], first["page_size"], len(first["items"])) == (32, 1, 10, 10)
    ids = [s["student_id"] for s in first["items"]]
    assert ids == sorted(ids)
    last = admin.get("/api/admin/students", params={"page": 4, "page_size": 10}).json()
    assert len(last["items"]) == 2 and not set(ids) & {s["student_id"] for s in last["items"]}


def test_search_matches_id_or_name_ignoring_case(admin, roster):
    assert [s["name"] for s in admin.get("/api/admin/students", params={"q": "student c"}).json()["items"]] == ["Student C"]
    assert {s["student_id"] for s in admin.get("/api/admin/students", params={"q": "1rv22cs1"}).json()["items"]} <= {s["student_id"] for s in admin.get("/api/admin/students", params={"page_size": 100}).json()["items"]}
    assert admin.get("/api/admin/students", params={"q": "nobody"}).json()["total"] == 0


def test_search_wildcards_are_plain_characters(admin, roster):
    assert admin.get("/api/admin/students", params={"q": "%"}).json()["total"] == 0
    assert admin.get("/api/admin/students", params={"q": "_"}).json()["total"] == 0


def test_filters_by_program_and_year_combine(admin, roster):
    body = admin.get("/api/admin/students", params={"program": "CSE", "year": 2}).json()
    assert body["total"] > 0 and {s["program"] for s in body["items"]} == {"CSE"} and {s["year"] for s in body["items"]} == {2}
    assert "CSE" in body["programs"] and "ISE" in body["programs"]


def test_the_list_says_who_has_an_account(admin, db):
    sign_up(TestClient(app))
    by_id = {s["student_id"]: s for s in admin.get("/api/admin/students").json()["items"]}
    assert by_id["1RV23IS101"]["has_account"] is True and by_id["1RV24IS219"]["has_account"] is False


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"year": 5}, {"q": "x" * 101}])
def test_bad_paging_or_filters_are_validation_errors(admin, params):
    assert admin.get("/api/admin/students", params=params).status_code == 422


# --- detail


def test_the_detail_gathers_records_registrations_and_tickets(admin, db):
    from helpers import ASHA_PROFILE, register_through_approval
    from app.services import action_service
    from uuid import UUID

    add_academic_data(db)
    sign_up(TestClient(app))
    register_through_approval(ASHA_PROFILE)
    confirmation = action_service.propose(ASHA_PROFILE, "create_grievance_ticket", {"category": "fees", "description": "The fee portal charged a late fee although I paid on time."})
    action_service.confirm(UUID(confirmation.action_id), ASHA_PROFILE)

    body = admin.get("/api/admin/students/1RV23IS101").json()

    assert (body["name"], body["program"], body["year"], body["semester"]) == ("Asha", "ISE", 3, 5)
    assert body["cgpa"] == 8.45 and body["account"] == {"email": "asha@example.com", "active": True}
    assert body["records"][0] == {"semester": 1, "course_code": "A101", "course": "Mathematics I", "credits": 4, "attended": 40, "total": 40, "grade": "A"}
    assert [r["event_id"] for r in body["registrations"]] == ["evt_ai_001"]
    assert [(t["ticket"], t["status"]) for t in body["tickets"]] == [("GR-00001", "open")]


def test_a_student_without_records_or_an_account_still_has_a_detail(admin, db):
    body = admin.get("/api/admin/students/1RV24IS219").json()
    assert (body["account"], body["cgpa"], body["records"], body["registrations"], body["tickets"]) == (None, None, [], [], [])


def test_an_unknown_student_is_not_found(admin):
    assert admin.get("/api/admin/students/9XX99XX999").status_code == 404


# --- import


def test_a_valid_file_adds_the_new_students(admin, db):
    body = admin.post("/api/admin/students/import", files=csv_file(GOOD))
    assert (body.status_code, body.json()) == (201, {"created": 2, "skipped_existing": []})
    with db() as session:
        added = session.get(Student, "1RV25CS501")
        assert (added.name, added.program, added.year) == ("Meera Nair", "CSE", 1)


def test_students_already_on_the_roster_are_left_alone_and_reported(admin, db):
    text = "student_id,name,program,year\n1RV23IS101,Someone Else,CSE,1\n1RV25CS501,Meera Nair,CSE,1\n"
    assert admin.post("/api/admin/students/import", files=csv_file(text)).json() == {"created": 1, "skipped_existing": ["1RV23IS101"]}
    with db() as session:
        assert session.get(Student, "1RV23IS101").name == "Asha"


def test_columns_may_come_in_any_order_with_a_byte_order_mark_and_extra_columns(admin, db):
    text = "﻿notes,year,name,student_id,program\nhi,2,Meera Nair,1RV25CS501,CSE\n"
    assert admin.post("/api/admin/students/import", files=csv_file(text)).json()["created"] == 1


def test_one_bad_row_means_nothing_is_imported(admin, db):
    text = GOOD + "BADID,Name,CSE,1\n1RV25CS503,,CSE,9\n"
    response = admin.post("/api/admin/students/import", files=csv_file(text))
    assert (response.status_code, response.json()["error_code"]) == (422, "invalid_rows")
    assert "3 problems" in response.json()["message"]
    with db() as session:
        assert session.get(Student, "1RV25CS501") is None


def test_a_student_repeated_in_the_file_is_an_error(admin):
    text = GOOD + "1RV25CS501,Again,CSE,1\n"
    response = admin.post("/api/admin/students/import", files=csv_file(text))
    assert response.status_code == 422 and "repeats line 2" in response.json()["message"]


@pytest.mark.parametrize(
    "text, code",
    [
        ("name,program\nA,B\n", "invalid_csv"),
        ("student_id,name,program,year\n", "invalid_csv"),
        ("", "invalid_csv"),
    ],
)
def test_a_file_without_the_right_columns_or_rows_is_refused(admin, text, code):
    response = admin.post("/api/admin/students/import", files=csv_file(text))
    assert (response.status_code, response.json()["error_code"]) == (422, code)


def test_a_file_that_is_not_text_is_refused(admin):
    files = {"file": ("s.csv", io.BytesIO(b"\xff\xfe\x00bad"), "text/csv")}
    assert admin.post("/api/admin/students/import", files=files).json()["error_code"] == "invalid_csv"


def test_an_oversized_file_is_refused(admin):
    big = "student_id,name,program,year\n" + "x" * (1024 * 1024 + 10)
    assert admin.post("/api/admin/students/import", files=csv_file(big)).status_code == 413


def test_too_many_rows_are_refused(admin, monkeypatch):
    from app.services import student_admin_service

    monkeypatch.setattr(student_admin_service, "MAX_IMPORT_ROWS", 1)
    assert admin.post("/api/admin/students/import", files=csv_file(GOOD)).json()["error_code"] == "too_many_rows"

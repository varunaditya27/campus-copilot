"""The committed operations demo data: reproducible from its generator, and following
the rules the knowledge documents state."""
import importlib.util
import json
from collections import Counter
from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from app.core import clock
from app.core.config import DATA_DIR
from app.db import session as db_session
from app.db.seed import seed
from app.services import campus_service, library_service, placement_service, study_room_service, support_service
from test_db_setup import _migrated_engine


def load(name):
    return json.loads((DATA_DIR / f"{name}.json").read_text())


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("generate_operations_data", DATA_DIR / "generate_operations_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_files_match_the_generator(generator):
    books = generator.build_books()
    assert books == load("books")
    assert generator.build_loans(books) == load("book_loans")
    assert generator.build_menu() == load("canteen_menu")
    assert generator.build_rooms() == load("study_rooms")
    assert generator.ROUTES == load("bus_routes")
    assert generator.build_lost_items() == load("lost_found_items")
    assert generator.build_counselling_slots() == load("counselling_slots")
    assert generator.build_drives() == load("placement_drives")


def test_no_book_has_more_copies_out_than_it_owns_and_reference_books_never_circulate():
    books = {b["book_id"]: b for b in load("books")}
    out = Counter(loan["book_id"] for loan in load("book_loans"))
    assert all(count <= books[book_id]["copies_total"] for book_id, count in out.items())
    assert not any(books[book_id]["reference_only"] for book_id in out)
    assert len({(l["book_id"], l["student_id"]) for l in load("book_loans")}) == len(load("book_loans"))
    assert all((date.fromisoformat(l["due_date"]) - date.fromisoformat(l["borrowed_on"])).days == 14 for l in load("book_loans"))
    assert len({b["isbn"] for b in books.values()}) == len(books)


def test_some_titles_are_all_out_so_a_hold_can_be_demonstrated():
    books = {b["book_id"]: b for b in load("books")}
    out = Counter(loan["book_id"] for loan in load("book_loans"))
    assert [books[i]["title"] for i, n in out.items() if n == books[i]["copies_total"]]


def test_there_are_eight_rooms_seating_four_to_eight():
    rooms = load("study_rooms")
    assert len(rooms) == 8 and all(4 <= r["capacity"] <= 8 for r in rooms)


def test_the_menu_follows_the_cafeteria_rules():
    rows = load("canteen_menu")
    assert {r["weekday"] for r in rows} == set(range(6)), "no Sunday menu"
    assert not [r for r in rows if r["meal"] == "dinner" and r["weekday"] == 5], "dinner is weekdays only"
    assert {r["price"] for r in rows if r["item"].startswith("Basic meal")} == {60}
    assert {r["price"] for r in rows if r["item"] == "Full thali"} == {90}
    for weekday in range(5):
        assert {r["meal"] for r in rows if r["weekday"] == weekday} == {"breakfast", "lunch", "evening", "dinner"}


def test_the_routes_follow_the_transport_document():
    routes = {r["route_code"]: r for r in load("bus_routes")}
    assert set(routes) == {"A", "B", "C", "TOWN"}
    assert routes["B"]["service"][0] == {"days": [0, 1, 2, 3, 4, 5, 6], "start": "07:00", "end": "22:00", "every_minutes": 15}
    assert routes["A"]["stops"][0] == "Main Gate" and routes["C"]["stops"][-1] == "Sports Complex"
    assert routes["TOWN"]["service"][0]["departures"] == ["10:00", "16:00"] and routes["TOWN"]["service"][0]["returns"] == ["13:00", "19:00"]


def test_counselling_slots_are_weekday_afternoons_in_the_future_and_none_is_named():
    slots = load("counselling_slots")
    assert all(date.fromisoformat(s["date"]).weekday() < 5 and s["start"] >= "14:00" for s in slots)
    assert min(s["date"] for s in slots) > "2026-10-15"
    assert sum(s["booked_by"] is not None for s in slots) == 3


def test_drive_criteria_follow_the_placement_cell_rules():
    drives = load("placement_drives")
    assert all(6.0 <= d["min_cgpa"] <= 7.5 and d["max_active_backlogs"] in (0, 1) for d in drives)
    assert {d["kind"] for d in drives} == {"full-time", "internship"}
    assert all(d["registration_deadline"] < d["date"] and d["date"] > "2026-10-15" for d in drives)


@pytest.fixture
def real(tmp_path, monkeypatch):
    engine, _ = _migrated_engine(tmp_path)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "SessionLocal", factory)
    monkeypatch.setattr(clock, "today", lambda: date(2026, 10, 15))
    with factory() as session:
        seed(session)
    yield
    engine.dispose()


def test_the_seeded_library_has_a_title_with_no_copy_to_reserve(real):
    (book,) = library_service.availability("introduction to algorithms")["books"]
    assert book["status"] == "all_out" and book["earliest_due_back"]


def test_seeded_rooms_menu_and_counselling_answer(real):
    assert study_room_service.availability("tomorrow")["rooms"]
    assert campus_service.canteen_menu("Monday")["meals"]
    assert support_service.counselling_slots("1RV23IS101")["slots"]


def test_seeded_drives_give_a_mixed_picture_for_a_real_student(real):
    results = {d["drive_id"]: placement_service.eligibility("1RV22IS305", d["drive_id"])["eligible"] for d in placement_service.drives()["drives"]}
    assert True in results.values() and False in results.values()

import json
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.config import DATA_DIR
from app.db import session as db_session
from app.db.models import Base
from app.db.seed import seed
from app.services.registration_service import create_registration
from helpers import all_registrations

BACKEND_DIR = Path(__file__).resolve().parents[1]
TABLES = {"students", "events", "registrations"}


def _alembic_config(url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _migrated_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_alembic_config(url), "head")
    return db_session.make_engine(url), url


def test_upgrade_head_creates_the_tables(tmp_path):
    engine, _ = _migrated_engine(tmp_path)
    assert TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_models_and_migrations_agree(tmp_path):
    engine, _ = _migrated_engine(tmp_path)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert differences == [], "models changed without a new migration"


def test_downgrade_base_removes_the_tables(tmp_path):
    engine, url = _migrated_engine(tmp_path)
    command.downgrade(_alembic_config(url), "base")
    assert TABLES.isdisjoint(inspect(engine).get_table_names())
    engine.dispose()


def _seeded(tmp_path, monkeypatch):
    engine, _ = _migrated_engine(tmp_path)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "SessionLocal", factory)
    with factory() as session:
        added = seed(session)
    return factory, added


def test_seed_loads_the_json_files(tmp_path, monkeypatch):
    _, added = _seeded(tmp_path, monkeypatch)
    files = {
        "students": "students", "events": "events", "registrations": "registrations",
        "courses": "courses", "student_profiles": "student_profiles", "academic_records": "academic_records",
        "faculty_members": "faculty_members", "course_offerings": "course_offerings",
        "timetable_slots": "timetable_slots", "exams": "exams", "fee_records": "fee_records",
        "books": "books", "book_loans": "book_loans", "canteen_menu": "canteen_menu", "study_rooms": "study_rooms",
        "bus_routes": "bus_routes", "lost_found_items": "lost_found_items", "counselling_slots": "counselling_slots",
        "placement_drives": "placement_drives",
        "event_details": "event_details",
    }
    expected = {name: len(json.loads((DATA_DIR / f"{file}.json").read_text())) for name, file in files.items()}
    assert added == expected


def test_seed_is_idempotent(tmp_path, monkeypatch):
    factory, _ = _seeded(tmp_path, monkeypatch)
    with factory() as session:
        assert set(seed(session).values()) == {0}


def test_new_registration_ids_continue_after_seeded_ones(tmp_path, monkeypatch):
    factory, _ = _seeded(tmp_path, monkeypatch)
    seeded_count = len(all_registrations(factory))
    students = json.loads((DATA_DIR / "students.json").read_text())
    taken = {(r.student_id, r.event_id) for r in all_registrations(factory)}
    student_id = next(s["student_id"] for s in students if (s["student_id"], "evt_ai_013") not in taken)

    result = create_registration(student_id, "evt_ai_013")

    assert result == {"success": True, "registration_id": f"REG-{seeded_count + 1:05d}"}


PREVIOUS_REVISION = "d951269155d5"  # before roles were added


def _insert_student_and_user(connection, student_id="1RV23IS101", name="Asha", email="asha@example.com"):
    connection.execute(
        text("INSERT INTO students (student_id, name, program, year) VALUES (:s, :n, 'ISE', 3)"),
        {"s": student_id, "n": name},
    )
    connection.execute(
        text(
            "INSERT INTO users (student_id, email, password_hash, is_active, created_at) "
            "VALUES (:s, :e, 'x', 1, '2026-01-01 00:00:00')"
        ),
        {"s": student_id, "e": email},
    )


def test_upgrading_keeps_existing_accounts_and_fills_in_their_names(tmp_path):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    config = _alembic_config(url)
    command.upgrade(config, PREVIOUS_REVISION)
    engine = db_session.make_engine(url)
    with engine.begin() as connection:
        _insert_student_and_user(connection)

    command.upgrade(config, "head")

    with engine.connect() as connection:
        row = connection.execute(text("SELECT role, name, student_id FROM users")).one()
    engine.dispose()
    assert tuple(row) == ("student", "Asha", "1RV23IS101")


def test_downgrading_drops_staff_accounts_but_keeps_students(tmp_path):
    url = f"sqlite:///{tmp_path / 'new.db'}"
    config = _alembic_config(url)
    command.upgrade(config, "head")
    engine = db_session.make_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO students (student_id, name, program, year) VALUES ('1RV23IS101', 'Asha', 'ISE', 3)")
        )
        for role, student_id, email in (("student", "1RV23IS101", "a@example.com"), ("admin", None, "root@example.com")):
            connection.execute(
                text(
                    "INSERT INTO users (role, name, student_id, email, password_hash, is_active, created_at) "
                    "VALUES (:r, 'N', :s, :e, 'x', 1, '2026-01-01 00:00:00')"
                ),
                {"r": role, "s": student_id, "e": email},
            )

    command.downgrade(config, PREVIOUS_REVISION)

    with engine.connect() as connection:
        emails = [row[0] for row in connection.execute(text("SELECT email FROM users"))]
    engine.dispose()
    assert emails == ["a@example.com"]

import json
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
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
    expected = {
        name: len(json.loads((DATA_DIR / f"{name}.json").read_text()))
        for name in ("students", "events", "registrations")
    }
    assert added == expected


def test_seed_is_idempotent(tmp_path, monkeypatch):
    factory, _ = _seeded(tmp_path, monkeypatch)
    with factory() as session:
        assert seed(session) == {"students": 0, "events": 0, "registrations": 0}


def test_new_registration_ids_continue_after_seeded_ones(tmp_path, monkeypatch):
    factory, _ = _seeded(tmp_path, monkeypatch)
    seeded_count = len(all_registrations(factory))
    students = json.loads((DATA_DIR / "students.json").read_text())
    taken = {(r.student_id, r.event_id) for r in all_registrations(factory)}
    student_id = next(s["student_id"] for s in students if (s["student_id"], "evt_ai_013") not in taken)

    result = create_registration(student_id, "evt_ai_013")

    assert result == {"success": True, "registration_id": f"REG-{seeded_count + 1:05d}"}

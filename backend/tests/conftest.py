import pytest
from sqlalchemy.orm import sessionmaker

from app.agent import agent
from app.db import session as db_session
from app.db.models import Base, Event, Student
from fakes import FakeGroq


def _event(event_id, name, category, capacity, registered, tags):
    return {
        "id": event_id,
        "name": name,
        "category": category,
        "date": "2026-09-01",
        "time": "10:00",
        "duration_minutes": 60,
        "venue": "Hall A",
        "capacity": capacity,
        "registered": registered,
        "organizer": "Test Club",
        "description": f"{name} description",
        "tags": tags,
    }


EVENTS = [
    _event("evt_ai_001", "AI Workshop", "artificial-intelligence", 10, 4, ["AI", "LLM"]),
    _event("evt_web_002", "Web Night", "web-development", 5, 5, ["react"]),
]
STUDENTS = [
    {"student_id": "1RV23IS101", "name": "Asha", "program": "ISE", "year": 3},
    {"student_id": "1RV24IS219", "name": "Ravi", "program": "CSE", "year": 2},
]


@pytest.fixture(autouse=True)
def _forbid_real_database(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("Test reached the real database; request the `db` fixture.")

    monkeypatch.setattr(db_session, "SessionLocal", refuse)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A throwaway SQLite database seeded with a small known dataset.

    The services open sessions through app.db.session.SessionLocal, so that
    one name is swapped for a factory bound to the temporary database.
    """
    engine = db_session.make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add_all([Student(**s) for s in STUDENTS])
        session.add_all([Event(**e) for e in EVENTS])

    monkeypatch.setattr(db_session, "SessionLocal", factory)
    yield factory
    engine.dispose()


@pytest.fixture
def use_fakes(monkeypatch):
    """Install a scripted fake Groq client and a stubbed retriever into the agent."""

    def install(*replies, chunks=()):
        client = FakeGroq(*replies)
        monkeypatch.setattr(agent, "get_groq_client", lambda: client)
        monkeypatch.setattr(agent, "retrieve", lambda message: list(chunks))
        return client

    return install

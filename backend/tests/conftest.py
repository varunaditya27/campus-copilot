import os
import uuid

os.environ.setdefault("JWT_SECRET", "test-only-secret-" + "x" * 32)

import pytest  # noqa: E402
from sqlalchemy.orm import sessionmaker

from app.agent import agent
from app.db import session as db_session
from app.db.models import Base, Event, Student
from fakes import FakeEmbedding, FakeGroq
from fakes import fake_llm


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
        monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(client))
        monkeypatch.setattr(agent, "retrieve", lambda message: list(chunks))
        return client

    return install


@pytest.fixture
def chroma_client(monkeypatch):
    """An in-memory Chroma with the fake embedding and a collection name of its own
    (Chroma's in-memory client is shared by the whole process), set up as the
    configured vector store."""
    import chromadb

    from app.rag import store as store_module

    monkeypatch.setattr(store_module, "get_embedding_function", lambda: FakeEmbedding())
    monkeypatch.setattr(store_module, "KNOWLEDGE_COLLECTION", f"test_{uuid.uuid4().hex}")
    monkeypatch.setattr(store_module, "VECTOR_STORE", "chroma")
    client = chromadb.EphemeralClient()
    monkeypatch.setattr(store_module, "_chroma_client", lambda: client)
    yield client
    try:
        client.delete_collection(name=store_module.KNOWLEDGE_COLLECTION)
    except Exception:
        pass


@pytest.fixture
def qdrant_client(monkeypatch):
    """An in-memory Qdrant with the fake embedding, set up as the configured vector store."""
    from qdrant_client import QdrantClient

    from app.rag import store as store_module

    monkeypatch.setattr(store_module, "get_embedding_function", lambda: FakeEmbedding())
    monkeypatch.setattr(store_module, "VECTOR_STORE", "qdrant")
    client = QdrantClient(":memory:")
    monkeypatch.setattr(store_module, "_qdrant_client", lambda: client)
    return client


@pytest.fixture(params=["chroma", "qdrant"])
def backend(request):
    """Each vector database in turn, configured but with nothing built in it yet."""
    request.getfixturevalue("chroma_client" if request.param == "chroma" else "qdrant_client")
    return request.param


@pytest.fixture
def store(backend):
    """A built, empty vector store. Tests using it run once per vector database."""
    from app.rag.store import create_store

    return create_store()

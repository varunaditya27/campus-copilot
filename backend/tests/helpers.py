from sqlalchemy import select

from app.db.models import Event, Registration
from app.models.auth import CurrentStudent


def all_registrations(factory):
    with factory() as session:
        return list(session.scalars(select(Registration).order_by(Registration.id)))


def event_registered(factory, event_id):
    with factory() as session:
        return session.get(Event, event_id).registered


ASHA = {"student_id": "1RV23IS101", "name": "Asha", "email": "asha@example.com", "password": "correct horse battery"}
RAVI = {"student_id": "1RV24IS219", "name": "Ravi", "email": "ravi@example.com", "password": "another long password"}


def sign_up(client, account=ASHA):
    """Register an account through the API; the client keeps the cookies."""
    response = client.post("/api/auth/register", json=account)
    assert response.status_code == 201, response.text
    return client


ASHA_PROFILE = CurrentStudent(
    user_id=1, student_id="1RV23IS101", name="Asha", program="ISE", year=3, email="asha@example.com"
)


ISE = "Information Science and Engineering"
CSE = "Computer Science and Engineering"
ADMIN = {"role": "admin", "name": "Root Admin", "email": "admin@example.com", "password": "admin password long"}
STAFF = {"role": "staff", "name": "Front Desk", "email": "staff@example.com", "password": "staff password long"}
FACULTY = {
    "role": "faculty", "name": "Dr. Rao", "email": "rao@example.com", "password": "faculty password long",
    "department": ISE, "office": "B-204", "office_hours": "Tue 2-4",
}
FACULTY_CSE = {**FACULTY, "name": "Dr. Iyer", "email": "iyer@example.com", "department": CSE}


def sign_in_as(account, **client_options):
    """Create a faculty/staff/admin account and return a client signed in as it."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.models.auth import NewStaffAccount
    from app.services import auth_service

    auth_service.create_staff_account(NewStaffAccount(**account))
    client = TestClient(app, **client_options)
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200, response.text
    return client


def insert_legacy_chunks(store, rows):
    """Put chunks into a store the way the first version of ingestion did, with only
    a document and section recorded (no file hash, settings signature or time).
    rows: (id, text, document, section)."""
    from qdrant_client import models

    from app.rag import store as store_module

    if isinstance(store, store_module.ChromaStore):
        store._collection.add(
            ids=[r[0] for r in rows],
            documents=[r[1] for r in rows],
            metadatas=[{"document": r[2], "section": r[3]} for r in rows],
        )
        return

    vectors = store._embed([r[1] for r in rows])
    store._client.upsert(
        store_module.KNOWLEDGE_COLLECTION,
        points=[
            models.PointStruct(
                id=store._point_id(chunk_id),
                vector=vector,
                payload={"id": chunk_id, "text": text, "document": document, "section": section},
            )
            for (chunk_id, text, document, section), vector in zip(rows, vectors)
        ],
    )

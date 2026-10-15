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

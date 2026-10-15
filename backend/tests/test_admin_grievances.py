import smtplib
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import app
from app.services import action_service, notification_service
from helpers import ADMIN, ASHA_PROFILE, FACULTY, RAVI_PROFILE, STAFF, sign_in_as, sign_up

TEXT = "The fee portal charged a late fee although I paid on time."


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(notification_service, "send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


@pytest.fixture
def tickets(db):
    """Asha (with an account) has two tickets; Ravi (without one) has one."""
    sign_up(TestClient(app))
    ids = []
    for who, category in ((ASHA_PROFILE, "fees"), (ASHA_PROFILE, "hostel"), (RAVI_PROFILE, "other")):
        confirmation = action_service.propose(who, "create_grievance_ticket", {"category": category, "description": TEXT})
        action_service.confirm(UUID(confirmation.action_id), who)
    return ids


@pytest.fixture
def staff(tickets):
    return sign_in_as(STAFF)


# --- who may use it


@pytest.mark.parametrize("account", [None, FACULTY])
def test_only_staff_and_admins_handle_grievances(tickets, account):
    client = sign_in_as(account) if account else TestClient(app)
    expected = 403 if account else 401
    assert client.get("/api/admin/grievances").status_code == expected
    assert client.put("/api/admin/grievances/1", json={"status": "open"}).status_code == expected


def test_a_student_cannot_see_or_change_tickets(tickets):
    client = sign_up(TestClient(app), {"student_id": "1RV24IS219", "name": "Ravi", "email": "ravi@example.com", "password": "another long password"})
    assert client.get("/api/admin/grievances").status_code == 403
    assert client.put("/api/admin/grievances/1", json={"status": "resolved", "resolution_note": "x"}).status_code == 403


def test_admins_can_do_it_too(tickets):
    assert sign_in_as(ADMIN).get("/api/admin/grievances").status_code == 200


# --- listing


def test_all_tickets_are_listed_newest_first_with_the_students_and_counts(staff):
    body = staff.get("/api/admin/grievances").json()
    assert [t["ticket"] for t in body["tickets"]] == ["GR-00003", "GR-00002", "GR-00001"]
    first = body["tickets"][2]
    assert (first["student_id"], first["student_name"], first["category"], first["status"], first["description"]) == ("1RV23IS101", "Asha", "fees", "open", TEXT)
    assert body["counts"] == {"open": 3, "in_progress": 0, "resolved": 0}


def test_the_list_can_be_filtered_by_status_and_counts_stay_overall(staff):
    staff.put("/api/admin/grievances/2", json={"status": "in_progress"})
    body = staff.get("/api/admin/grievances", params={"status": "in_progress"}).json()
    assert [t["ticket"] for t in body["tickets"]] == ["GR-00002"] and body["counts"] == {"open": 2, "in_progress": 1, "resolved": 0}
    assert staff.get("/api/admin/grievances", params={"status": "weird"}).status_code == 422


# --- updating


def test_moving_a_ticket_changes_its_status_and_the_student_sees_it(staff, outbox):
    response = staff.put("/api/admin/grievances/GR-00001", json={"status": "in_progress", "resolution_note": "Looking into the portal logs."})
    assert response.status_code == 200 and response.json()["status"] == "in_progress"
    from app.services import support_service

    seen = support_service.grievance_status("1RV23IS101", "GR-00001")
    assert (seen["status"], seen["resolution_note"]) == ("in_progress", "Looking into the portal logs.")


def test_resolving_needs_a_note(staff):
    response = staff.put("/api/admin/grievances/1", json={"status": "resolved"})
    assert (response.status_code, response.json()["error_code"]) == (422, "note_required")
    response = staff.put("/api/admin/grievances/1", json={"status": "resolved", "resolution_note": "   "})
    assert response.json()["error_code"] == "note_required"
    assert staff.put("/api/admin/grievances/1", json={"status": "resolved", "resolution_note": "Late fee reversed."}).json()["status"] == "resolved"


def test_a_ticket_can_be_reopened(staff):
    staff.put("/api/admin/grievances/1", json={"status": "resolved", "resolution_note": "Done."})
    assert staff.put("/api/admin/grievances/1", json={"status": "open"}).json()["status"] == "open"


@pytest.mark.parametrize("body", [{"status": "closed"}, {}, {"status": "open", "resolution_note": "x" * 2001}])
def test_bad_updates_are_validation_errors(staff, body):
    assert staff.put("/api/admin/grievances/1", json=body).status_code == 422


@pytest.mark.parametrize("ticket", ["99", "GR-00099", "banana"])
def test_an_unknown_ticket_is_not_found(staff, ticket):
    assert staff.put(f"/api/admin/grievances/{ticket}", json={"status": "open"}).status_code == 404


def test_tickets_can_be_addressed_by_number_or_reference(staff):
    for ref in ("1", "GR-00001", "gr-1"):
        assert staff.put(f"/api/admin/grievances/{ref}", json={"status": "in_progress"}).json()["ticket"] == "GR-00001"


# --- email


def test_the_student_is_emailed_when_the_status_changes(staff, outbox):
    staff.put("/api/admin/grievances/1", json={"status": "resolved", "resolution_note": "Late fee reversed."})
    assert len(outbox) == 1
    to, subject, body = outbox[0]
    assert (to, subject) == ("asha@example.com", "Your grievance GR-00001 is now resolved")
    assert "Hello Asha" in body and "Late fee reversed." in body


def test_no_email_when_only_the_note_changes(staff, outbox):
    staff.put("/api/admin/grievances/1", json={"status": "in_progress", "resolution_note": "first"})
    outbox.clear()
    staff.put("/api/admin/grievances/1", json={"status": "in_progress", "resolution_note": "second"})
    assert outbox == []


def test_a_student_without_an_account_gets_no_email_but_the_update_works(staff, outbox):
    assert staff.put("/api/admin/grievances/3", json={"status": "in_progress"}).status_code == 200
    assert outbox == []


def test_a_failing_mail_server_never_fails_the_update(staff, monkeypatch):
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.invalid")
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: (_ for _ in ()).throw(OSError("unreachable")))
    assert staff.put("/api/admin/grievances/1", json={"status": "in_progress"}).status_code == 200


# --- the mail sender itself


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout, self.actions, self.messages = host, port, timeout, [], []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.actions.append("starttls")

    def login(self, user, password):
        self.actions.append(("login", user, password))

    def send_message(self, message):
        self.messages.append(message)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances.clear()
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.org")
    monkeypatch.setattr(config, "SMTP_PORT", 2525)
    monkeypatch.setattr(config, "SMTP_USER", "mailer")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(config, "SMTP_STARTTLS", True)


def test_an_email_is_built_and_sent_over_an_encrypted_login(smtp):
    assert notification_service.send_email("a@b.c", "Hi", "Body text") is True
    (server,) = FakeSMTP.instances
    assert (server.host, server.port, server.timeout) == ("smtp.example.org", 2525, 10)
    assert server.actions == ["starttls", ("login", "mailer", "secret")], "encryption must come before the password"
    (message,) = server.messages
    assert (message["To"], message["Subject"], message["From"]) == ("a@b.c", "Hi", config.SMTP_FROM) and "Body text" in message.get_content()


def test_a_local_test_server_can_skip_encryption_and_login(smtp, monkeypatch):
    monkeypatch.setattr(config, "SMTP_STARTTLS", False)
    monkeypatch.setattr(config, "SMTP_USER", "")
    notification_service.send_email("a@b.c", "Hi", "x")
    assert FakeSMTP.instances[0].actions == []


def test_without_a_mail_server_nothing_is_sent_and_nothing_breaks(monkeypatch, caplog):
    monkeypatch.setattr(config, "SMTP_HOST", "")
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: pytest.fail("must not connect"))
    with caplog.at_level("INFO"):
        assert notification_service.send_email("a@b.c", "Hi", "x") is False
    assert "SMTP_HOST is not set" in caplog.text


def test_a_failure_is_logged_and_reported_as_not_sent(smtp, monkeypatch, caplog):
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: (_ for _ in ()).throw(ConnectionRefusedError("no")))
    assert notification_service.send_email("a@b.c", "Hi", "x") is False
    assert "Could not send email" in caplog.text


def test_the_status_email_names_the_ticket_and_includes_the_note():
    subject, body = notification_service.ticket_status_email("Asha", "GR-00007", "in_progress", None)
    assert subject == "Your grievance GR-00007 is now being looked into" and "Note from the committee" not in body

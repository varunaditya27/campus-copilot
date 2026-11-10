import base64
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from pywebpush import WebPushException
from sqlalchemy import select

from app.cli import main as cli_main
from app.core import clock
from app.db.models import PushSubscription, Registration
from app.main import app
from app.models.notifications import is_push_service_url
from app.services import action_service, push_service
from helpers import ADMIN, ASHA, ASHA_PROFILE, RAVI, RAVI_PROFILE, register_through_approval, sign_in_as, sign_up

FCM = "https://fcm.googleapis.com/fcm/send/abc"
MOZILLA = "https://updates.push.services.mozilla.com/wpush/v2/xyz"
ASHA_ID, RAVI_ID = ASHA["student_id"], RAVI["student_id"]


def browser(endpoint=FCM):
    return {"endpoint": endpoint, "keys": {"p256dh": "BPkey", "auth": "authkey"}}


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(push_service, "VAPID_PUBLIC_KEY", "public-key")
    monkeypatch.setattr(push_service, "VAPID_PRIVATE_KEY", "private-key")
    monkeypatch.setattr(push_service, "VAPID_SUBJECT", "mailto:admin@example.com")


@pytest.fixture
def pushes(monkeypatch):
    """Stands in for the push services: records each message and can be told an endpoint fails."""

    class Recorder:
        def __init__(self):
            self.calls, self.failures = [], {}

        def __call__(self, **kwargs):
            self.calls.append(kwargs)
            failure = self.failures.get(kwargs["subscription_info"]["endpoint"])
            if failure is not None:
                raise failure

    recorder = Recorder()
    monkeypatch.setattr(push_service, "webpush", recorder)
    return recorder


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app), ASHA)


def stored(db):
    with db() as session:
        return [(s.student_id, s.endpoint) for s in session.scalars(select(PushSubscription).order_by(PushSubscription.id))]


def gone(status):
    return WebPushException("gone", response=SimpleNamespace(status_code=status))


# --- which addresses the server will send to


@pytest.mark.parametrize(
    "url",
    [FCM, MOZILLA, "https://web.push.apple.com/Qabc", "https://wns2-par02p.notify.windows.com/w/?token=x"],
)
def test_the_known_push_services_are_accepted(url):
    assert is_push_service_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://fcm.googleapis.com/fcm/send/abc",
        "https://127.0.0.1/x",
        "https://localhost/x",
        "https://169.254.169.254/latest/meta-data",
        "https://fcm.googleapis.com.evil.example/x",
        "https://evilfcm.googleapis.com/x",
        "https://user:pw@fcm.googleapis.com/x",
        "https://fcm.googleapis.com:8443/x",
        "ftp://fcm.googleapis.com/x",
        "",
    ],
)
def test_anything_else_is_refused(url):
    assert not is_push_service_url(url)


# --- the endpoints


def test_a_student_gets_the_public_key_when_push_is_set_up(asha, configured):
    assert asha.get("/api/notifications/public-key").json() == {"public_key": "public-key"}


def test_without_keys_push_is_unavailable(asha):
    assert asha.get("/api/notifications/public-key").status_code == 404
    response = asha.post("/api/notifications/subscribe", json=browser())
    assert response.status_code == 404 and response.json()["error_code"] == "push_unavailable"


def test_subscribing_twice_from_one_browser_keeps_one_row(db, asha, configured):
    assert asha.post("/api/notifications/subscribe", json=browser()).status_code == 204
    assert asha.post("/api/notifications/subscribe", json=browser()).status_code == 204
    assert stored(db) == [(ASHA_ID, FCM)]


def test_a_browser_used_by_another_student_moves_to_them(db, asha, configured):
    asha.post("/api/notifications/subscribe", json=browser())
    ravi = sign_up(TestClient(app), RAVI)
    ravi.post("/api/notifications/subscribe", json=browser())
    assert stored(db) == [(RAVI_ID, FCM)]


def test_an_address_that_is_not_a_push_service_is_refused(db, asha, configured):
    response = asha.post("/api/notifications/subscribe", json=browser("https://127.0.0.1/hook"))
    assert response.status_code == 422 and stored(db) == []


def test_unsubscribing_removes_only_the_students_own_browser(db, asha, configured):
    asha.post("/api/notifications/subscribe", json=browser(FCM))
    ravi = sign_up(TestClient(app), RAVI)
    ravi.post("/api/notifications/subscribe", json=browser(MOZILLA))

    ravi.post("/api/notifications/unsubscribe", json={"endpoint": FCM})
    assert stored(db) == [(ASHA_ID, FCM), (RAVI_ID, MOZILLA)]

    asha.post("/api/notifications/unsubscribe", json={"endpoint": FCM})
    assert stored(db) == [(RAVI_ID, MOZILLA)]


def test_only_students_can_use_notifications(db, configured):
    assert TestClient(app).get("/api/notifications/public-key").status_code == 401
    assert sign_in_as(ADMIN).get("/api/notifications/public-key").status_code == 403


# --- sending


def test_a_message_goes_to_every_browser_the_student_has(db, asha, configured, pushes):
    asha.post("/api/notifications/subscribe", json=browser(FCM))
    asha.post("/api/notifications/subscribe", json=browser(MOZILLA))
    ravi = sign_up(TestClient(app), RAVI)
    ravi.post("/api/notifications/subscribe", json=browser("https://web.push.apple.com/Qabc"))

    assert push_service.notify(ASHA_ID, "Title", "Body text", "/events/e1") == 2

    assert [c["subscription_info"]["endpoint"] for c in pushes.calls] == [FCM, MOZILLA]
    first = pushes.calls[0]
    assert json.loads(first["data"]) == {"title": "Title", "body": "Body text", "url": "/events/e1"}
    assert first["subscription_info"]["keys"] == {"p256dh": "BPkey", "auth": "authkey"}
    assert first["vapid_private_key"] == "private-key" and first["vapid_claims"] == {"sub": "mailto:admin@example.com"}
    # The library adds fields to the claims it is given, so each message needs its own copy.
    assert pushes.calls[0]["vapid_claims"] is not pushes.calls[1]["vapid_claims"]


@pytest.mark.parametrize("status", [404, 410])
def test_a_browser_the_push_service_says_is_gone_is_forgotten(db, asha, configured, pushes, status):
    asha.post("/api/notifications/subscribe", json=browser(FCM))
    asha.post("/api/notifications/subscribe", json=browser(MOZILLA))
    pushes.failures[FCM] = gone(status)

    assert push_service.notify(ASHA_ID, "T", "B") == 1
    assert stored(db) == [(ASHA_ID, MOZILLA)]


def test_any_other_failure_keeps_the_browser_and_never_raises(db, asha, configured, pushes):
    asha.post("/api/notifications/subscribe", json=browser(FCM))
    pushes.failures[FCM] = gone(500)
    assert push_service.notify(ASHA_ID, "T", "B") == 0
    assert stored(db) == [(ASHA_ID, FCM)]

    pushes.failures[FCM] = RuntimeError("network down")
    assert push_service.notify(ASHA_ID, "T", "B") == 0


def test_nothing_is_sent_when_push_is_not_set_up(db, asha, pushes, monkeypatch):
    monkeypatch.setattr(push_service, "VAPID_PUBLIC_KEY", "public-key")
    monkeypatch.setattr(push_service, "VAPID_PRIVATE_KEY", "private-key")
    monkeypatch.setattr(push_service, "VAPID_SUBJECT", "mailto:admin@example.com")
    asha.post("/api/notifications/subscribe", json=browser())
    monkeypatch.setattr(push_service, "VAPID_PRIVATE_KEY", "")

    assert push_service.notify(ASHA_ID, "T", "B") == 0 and pushes.calls == []


def test_a_stored_address_that_is_no_longer_allowed_is_dropped_not_contacted(db, configured, pushes):
    with db.begin() as session:
        session.add(PushSubscription(student_id=ASHA_ID, endpoint="https://127.0.0.1/hook", p256dh="k", auth="a"))

    assert push_service.notify(ASHA_ID, "T", "B") == 0
    assert pushes.calls == [] and stored(db) == []


# --- who is told, and when


@pytest.fixture
def told(monkeypatch):
    calls = []
    monkeypatch.setattr(push_service, "notify", lambda student_id, title, body, url="/": calls.append((student_id, title, body, url)) or 1)
    return calls


def test_a_student_is_told_when_their_registration_is_confirmed(db, told):
    register_through_approval(ASHA_PROFILE)
    assert len(told) == 1
    student_id, title, body, url = told[0]
    assert student_id == ASHA_ID and "registered" in title.lower()
    assert "AI Workshop" in body and url == "/events/evt_ai_001"


def test_the_student_who_gets_a_freed_seat_is_told(db, told, monkeypatch):
    moment = datetime(2026, 8, 20, 9, 0)  # before the events, which are on 2026-09-01
    monkeypatch.setattr(clock, "now", lambda: moment)
    monkeypatch.setattr(clock, "today", lambda: moment.date())
    with db.begin() as session:
        session.add(Registration(registration_id="REG-X", student_id=ASHA_ID, event_id="evt_web_002", registered_at=datetime.now(timezone.utc)))
    confirmation = action_service.propose(RAVI_PROFILE, "join_event_waitlist", {"event_id": "evt_web_002"})
    action_service.confirm(UUID(confirmation.action_id), RAVI_PROFILE)
    told.clear()

    confirmation = action_service.propose(ASHA_PROFILE, "cancel_event_registration", {"event_id": "evt_web_002"})
    action_service.confirm(UUID(confirmation.action_id), ASHA_PROFILE)

    assert [(c[0], c[3]) for c in told] == [(RAVI_ID, "/events/evt_web_002")]
    assert "Web Night" in told[0][2]


# --- the key pair


def test_the_command_makes_a_key_pair_the_browser_and_the_server_can_both_use(capsys):
    assert cli_main(["create-vapid-keys"]) == 0
    values = dict(line.strip().split("=", 1) for line in capsys.readouterr().out.splitlines() if line.startswith("VAPID_"))

    public = base64.urlsafe_b64decode(values["VAPID_PUBLIC_KEY"] + "==")
    assert len(public) == 65 and public[0] == 4  # an uncompressed P-256 point, which is what browsers expect
    pair = Vapid.from_string(values["VAPID_PRIVATE_KEY"])
    assert pair.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint) == public

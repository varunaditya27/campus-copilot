import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select

from app.core.config import VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_SUBJECT
from app.db import session as db_session
from app.db.models import PushSubscription
from app.models.notifications import PushSubscriptionIn, is_push_service_url

logger = logging.getLogger(__name__)

PUSH_TIMEOUT_SECONDS = 10
# How long a push service holds a message for a browser that is offline.
PUSH_TTL_SECONDS = 24 * 60 * 60
# The push service answers these when a browser has unsubscribed or been uninstalled.
SUBSCRIPTION_GONE = (404, 410)


def is_configured() -> bool:
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY and VAPID_SUBJECT)


def public_key() -> str | None:
    return VAPID_PUBLIC_KEY if is_configured() else None


def subscribe(student_id: str, subscription: PushSubscriptionIn) -> None:
    with db_session.SessionLocal() as db:
        row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == subscription.endpoint))
        if row is None:
            db.add(
                PushSubscription(
                    student_id=student_id,
                    endpoint=subscription.endpoint,
                    p256dh=subscription.keys.p256dh,
                    auth=subscription.keys.auth,
                )
            )
        else:  # the same browser again, maybe now signed in as someone else
            row.student_id = student_id
            row.p256dh = subscription.keys.p256dh
            row.auth = subscription.keys.auth
        db.commit()


def unsubscribe(student_id: str, endpoint: str) -> None:
    with db_session.SessionLocal() as db:
        db.execute(
            delete(PushSubscription).where(PushSubscription.endpoint == endpoint, PushSubscription.student_id == student_id)
        )
        db.commit()


def _send(subscription: PushSubscription, payload: str) -> str:
    """"sent", "gone" (forget this browser) or "failed" (try again another time)."""
    if not is_push_service_url(subscription.endpoint):
        return "gone"
    try:
        webpush(
            subscription_info={"endpoint": subscription.endpoint, "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth}},
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},  # a new dict each time: the library adds fields to it
            ttl=PUSH_TTL_SECONDS,
            timeout=PUSH_TIMEOUT_SECONDS,
        )
        return "sent"
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in SUBSCRIPTION_GONE:
            return "gone"
        logger.warning("Push service refused a message (status %s)", status)
    except Exception:
        logger.warning("Could not reach a push service", exc_info=True)
    return "failed"


def notify(student_id: str, title: str, body: str, url: str = "/") -> int:
    """Send a message to every browser the student agreed to. Returns how many received it.
    Never raises: a notification must not break what triggered it."""
    if not is_configured():
        return 0
    # shortcut: sends one after another in the caller's thread (up to 10 s each), so move this to a
    # background task if students have many browsers or the push services are slow.
    payload = json.dumps({"title": title, "body": body, "url": url})
    delivered = 0
    try:
        with db_session.SessionLocal() as db:
            rows = db.scalars(
                select(PushSubscription).where(PushSubscription.student_id == student_id).order_by(PushSubscription.id)
            ).all()
            for row in rows:
                outcome = _send(row, payload)
                if outcome == "gone":
                    db.delete(row)
                delivered += outcome == "sent"
            db.commit()
    except Exception:
        logger.exception("Could not send push notifications")
    return delivered

from fastapi import APIRouter, Response

from app.api.deps import SignedInStudent
from app.core.errors import AppError
from app.models.notifications import PushEndpoint, PushSubscriptionIn
from app.services import push_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _require_push() -> None:
    if not push_service.is_configured():
        raise AppError(404, "push_unavailable", "Push notifications are not set up on this server.")


@router.get("/public-key")
def public_key(student: SignedInStudent) -> dict:
    """The key a browser needs to subscribe to this server's notifications."""
    _require_push()
    return {"public_key": push_service.public_key()}


@router.post("/subscribe", status_code=204)
def subscribe(body: PushSubscriptionIn, student: SignedInStudent) -> Response:
    _require_push()
    push_service.subscribe(student.student_id, body)
    return Response(status_code=204)


@router.post("/unsubscribe", status_code=204)
def unsubscribe(body: PushEndpoint, student: SignedInStudent) -> Response:
    push_service.unsubscribe(student.student_id, body.endpoint)
    return Response(status_code=204)

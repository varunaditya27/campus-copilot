from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SignedInStudent
from app.models.actions import ActionOutcome
from app.services import action_service

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.post("/{action_id}/confirm")
def confirm(action_id: UUID, student: SignedInStudent) -> ActionOutcome:
    """Approve something the assistant proposed. This is the only way a proposed
    action runs: the model cannot call it."""
    return action_service.confirm(action_id, student)


@router.post("/{action_id}/cancel")
def cancel(action_id: UUID, student: SignedInStudent) -> ActionOutcome:
    return action_service.cancel(action_id, student)

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from app.actions.base import ActionError
from app.actions.registry import ACTIONS
from app.core.errors import AppError
from app.db import session as db_session
from app.db.models import PendingAction
from app.models.actions import ActionOutcome, Confirmation, ConfirmationLine
from app.models.auth import CurrentStudent

logger = logging.getLogger(__name__)

# How long a student has to approve what the assistant proposed.
CONFIRMATION_MINUTES = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)  # SQLite drops the zone


def propose(student: CurrentStudent, name: str, args: dict) -> Confirmation:
    """Check an action the model asked for and keep it, waiting for approval.

    Raises ActionError (with a reason fit to tell the student) if it cannot go ahead.
    """
    prepared = ACTIONS[name].prepare(args, student)
    row = PendingAction(
        student_id=student.student_id,
        action=name,
        params=prepared.params,
        title=prepared.title,
        lines=[line.model_dump() for line in prepared.lines],
        expires_at=_now() + timedelta(minutes=CONFIRMATION_MINUTES),
    )
    with db_session.SessionLocal() as db:
        db.add(row)
        db.commit()
        return Confirmation(
            action_id=str(row.id),
            action=name,
            title=row.title,
            lines=[ConfirmationLine(**line) for line in row.lines],
            expires_at=_aware(row.expires_at),
        )


def _outcome(row: PendingAction) -> ActionOutcome:
    result = row.result or {}
    return ActionOutcome(
        action_id=str(row.id),
        status=row.status if row.status in ("confirmed", "cancelled", "failed") else "failed",
        success=row.status == "confirmed",
        message=result.get("message", ""),
        details=result.get("details", {}),
    )


def _owned(db, action_id: UUID, student: CurrentStudent) -> PendingAction:
    row = db.scalar(
        select(PendingAction).where(PendingAction.id == action_id, PendingAction.student_id == student.student_id)
    )
    if row is None:
        # Someone else's action looks exactly like one that does not exist.
        raise AppError(404, "not_found", "No such pending action.")
    return row


def _claim(db, row: PendingAction, new_status: str) -> bool:
    """Move a still-pending action to a new status. Only one request can win."""
    claimed = db.execute(
        update(PendingAction)
        .where(PendingAction.id == row.id, PendingAction.status == "pending")
        .values(status=new_status, resolved_at=_now())
    )
    db.commit()
    return claimed.rowcount == 1


def confirm(action_id: UUID, student: CurrentStudent) -> ActionOutcome:
    """Run the stored action. Approving twice runs it once and returns the same answer."""
    with db_session.SessionLocal() as db:
        row = _owned(db, action_id, student)
        if row.status == "confirmed":
            if row.result is None:
                raise AppError(409, "action_in_progress", "This action is still being carried out.")
            return _outcome(row)
        if row.status in ("cancelled", "failed", "expired"):
            raise AppError(409, f"action_{row.status}", f"This action was already {row.status}.")
        if _aware(row.expires_at) <= _now():
            _claim(db, row, "expired")
            raise AppError(410, "action_expired", "This took too long to approve. Please ask again.")
        if not _claim(db, row, "confirmed"):
            raise AppError(409, "action_in_progress", "This action is already being handled.")
        name, params = row.action, dict(row.params)

    try:
        done = ACTIONS[name].execute(params, student)
        result = {"success": True, "message": done.message, "details": done.details}
        final = "confirmed"
    except ActionError as exc:
        result, final = {"success": False, "message": str(exc), "details": {}}, "failed"
    except Exception:
        logger.exception("Action %s failed", name)
        result = {"success": False, "message": "Something went wrong, so nothing was done. Please try again.", "details": {}}
        final = "failed"

    with db_session.SessionLocal() as db:
        db.execute(update(PendingAction).where(PendingAction.id == action_id).values(status=final, result=result))
        db.commit()
        return _outcome(db.get(PendingAction, action_id))


def cancel(action_id: UUID, student: CurrentStudent) -> ActionOutcome:
    with db_session.SessionLocal() as db:
        row = _owned(db, action_id, student)
        if row.status == "cancelled":
            return _outcome(row)
        if row.status != "pending":
            raise AppError(409, f"action_{row.status}", f"This action was already {row.status}.")
        if not _claim(db, row, "cancelled"):
            raise AppError(409, "action_in_progress", "This action is already being handled.")
        db.execute(
            update(PendingAction).where(PendingAction.id == action_id).values(result={"message": "Cancelled. Nothing was done.", "details": {}})
        )
        db.commit()
        return _outcome(db.get(PendingAction, action_id))

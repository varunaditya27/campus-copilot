from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel, Field

from app.api.deps import StaffUser
from app.core.errors import AppError
from app.services import notification_service, support_service

router = APIRouter(prefix="/api/admin/grievances", tags=["admin"])


class GrievanceUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
    resolution_note: str | None = Field(default=None, max_length=support_service.MAX_NOTE_CHARS)


@router.get("")
def list_grievances(
    staff: StaffUser, status: Annotated[Literal["open", "in_progress", "resolved"] | None, Query()] = None
) -> dict:
    return support_service.list_grievances(status)


@router.put("/{ticket_id}")
def update_grievance(ticket_id: str, data: GrievanceUpdate, staff: StaffUser, background: BackgroundTasks) -> dict:
    """Move a ticket to a status and set its resolution note. The student is emailed
    when the status changes, after the response is sent, so a mail problem never fails the update."""
    parsed = support_service.parse_ticket_id(ticket_id)
    if parsed is None:
        raise AppError(404, "not_found", "No such ticket.")
    result = support_service.update_grievance(parsed, data.status, data.resolution_note)
    ticket = result["ticket"]
    if result["status_changed"] and result["student_email"]:
        subject, body = notification_service.ticket_status_email(
            ticket["student_name"], ticket["ticket"], ticket["status"], ticket["resolution_note"]
        )
        background.add_task(notification_service.send_email, result["student_email"], subject, body)
    return ticket

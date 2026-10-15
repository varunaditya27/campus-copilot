from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import StaffUser
from app.core.errors import AppError
from app.models.registration import CSV_COLUMNS, RegistrationRecord
from app.services import event_service, export_service, registration_service

router = APIRouter(prefix="/api/staff", tags=["staff"])

EventFilter = Annotated[str | None, Query(max_length=64)]

def _records(event_id: str | None) -> list[RegistrationRecord]:
    if event_id is not None and event_service.get_event(event_id) is None:
        raise AppError(404, "not_found", f"Event '{event_id}' not found")
    return registration_service.list_registrations(event_id)


@router.get("/registrations")
def registrations(user: StaffUser, event_id: EventFilter = None) -> list[RegistrationRecord]:
    return _records(event_id)


@router.get("/registrations/export")
def export_registrations(user: StaffUser, event_id: EventFilter = None) -> Response:
    content = export_service.to_csv(CSV_COLUMNS, (list(r.model_dump().values()) for r in _records(event_id)))
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="registrations.csv"'},
    )

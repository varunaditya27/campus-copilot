from fastapi import APIRouter, Response

from app.api.deps import EventEditor
from app.models.events import CampusEvent, EventInput
from app.models.registration import CSV_COLUMNS
from app.services import event_service, export_service

router = APIRouter(prefix="/api/admin/events", tags=["admin"])


@router.post("", status_code=201)
def create_event(data: EventInput, editor: EventEditor) -> CampusEvent:
    return event_service.create_event(data, editor)


@router.put("/{event_id}")
def update_event(event_id: str, data: EventInput, editor: EventEditor) -> CampusEvent:
    return event_service.update_event(event_id, data, editor)


@router.delete("/{event_id}")
def delete_event(event_id: str, editor: EventEditor, force: bool = False) -> dict:
    """Delete an event. If students are registered this answers 409 until called with force=true."""
    return event_service.delete_event(event_id, editor, force)


@router.get("/{event_id}/registrations")
def registrations(event_id: str, editor: EventEditor) -> dict:
    return event_service.event_roster(event_id, editor)


@router.post("/{event_id}/registrations/export")
def export_registrations(event_id: str, editor: EventEditor) -> Response:
    roster = event_service.event_roster(event_id, editor)
    content = export_service.to_csv(CSV_COLUMNS, (list(r.model_dump().values()) for r in roster["registrations"]))
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="registrations-{event_id}.csv"'},
    )

from fastapi import APIRouter

from app.api.deps import EventEditor
from app.models.events import CampusEvent, EventInput
from app.services import event_service

router = APIRouter(prefix="/api/admin/events", tags=["admin"])


@router.post("", status_code=201)
def create_event(data: EventInput, editor: EventEditor) -> CampusEvent:
    return event_service.create_event(data, editor)


@router.put("/{event_id}")
def update_event(event_id: str, data: EventInput, editor: EventEditor) -> CampusEvent:
    return event_service.update_event(event_id, data, editor)

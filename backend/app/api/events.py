from fastapi import APIRouter, HTTPException

from app.models.events import CampusEvent
from app.services import event_service

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events() -> list[CampusEvent]:
    return event_service.list_events()


@router.get("/{event_id}")
def get_event(event_id: str) -> CampusEvent:
    event = event_service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return event

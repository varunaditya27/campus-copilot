import json

from app.core.config import DATA_DIR
from app.models.events import CampusEvent

_EVENTS_FILE = DATA_DIR / "events.json"


def _load_events() -> list[CampusEvent]:
    raw = json.loads(_EVENTS_FILE.read_text())
    return [CampusEvent(**item) for item in raw]


def list_events() -> list[CampusEvent]:
    return _load_events()


def get_event(event_id: str) -> CampusEvent | None:
    for event in _load_events():
        if event.id == event_id:
            return event
    return None

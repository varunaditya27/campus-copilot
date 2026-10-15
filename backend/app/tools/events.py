from typing import Annotated

from pydantic import Field, validate_call

from app.services import event_service


@validate_call
def search_events(query: Annotated[str, Field(max_length=200)]) -> list[dict]:
    """Keyword search over structured event data (not semantic — that's what
    RAG is for). A campus event is structured data with a fixed schema, so a
    simple keyword match over name/category/description/tags is sufficient
    and far cheaper than embedding every event."""
    words = [w for w in query.lower().split() if len(w) > 2]

    matches = []
    for event in event_service.list_events():
        haystack = " ".join(
            [event.name, event.category, event.description, *event.tags]
        ).lower()
        if not words or any(word in haystack for word in words):
            matches.append(event.model_dump())
    return matches


@validate_call
def check_event_availability(event_id: Annotated[str, Field(max_length=64)]) -> dict:
    event = event_service.get_event(event_id)
    if event is None:
        return {"error": f"No event found with id '{event_id}'"}

    remaining = event.capacity - event.registered
    return {"available": remaining > 0, "remaining_seats": remaining}

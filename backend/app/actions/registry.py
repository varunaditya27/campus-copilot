from app.actions import campus, events, registration, support
from app.actions.base import ActionSpec

# Every action the assistant may propose. The model can ask for any of these;
# none of them runs until the student approves it.
ACTIONS: dict[str, ActionSpec] = {
    spec.name: spec
    for spec in (
        registration.SPEC,
        campus.RESERVE_BOOK,
        campus.BOOK_ROOM,
        campus.REPORT_MAINTENANCE,
        campus.SUBMIT_LOST_ITEM,
        support.CREATE_GRIEVANCE,
        support.BOOK_COUNSELLING,
        events.CANCEL_REGISTRATION,
        events.JOIN_WAITLIST,
        events.SUBMIT_FEEDBACK,
    )
}

ACTION_SCHEMAS = [spec.schema for spec in ACTIONS.values()]

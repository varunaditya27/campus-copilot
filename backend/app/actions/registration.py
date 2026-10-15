from app.actions.base import ActionError, ActionSpec, Done, Prepared
from app.models.actions import ConfirmationLine
from app.models.auth import CurrentStudent
from app.services import event_service, registration_service

NAME = "register_for_event"

SCHEMA = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": (
            "Prepare an event registration for the signed-in student to confirm. "
            "Call this once you have a real event_id (from search_events) and they've "
            "asked to register. This does NOT complete the registration -- it shows the "
            "student a confirmation card; the actual registration only happens if they "
            "approve it."
        ),
        "parameters": {
            "type": "object",
            "properties": {"event_id": {"type": "string"}},
            "required": ["event_id"],
        },
    },
}


def prepare(args: dict, student: CurrentStudent) -> Prepared:
    event_id = args.get("event_id")
    event = event_service.get_event(event_id) if isinstance(event_id, str) else None
    if event is None:
        raise ActionError(
            "I couldn't find that event to register you for -- could you confirm which event you mean?"
        )
    if event.registered >= event.capacity:
        raise ActionError(f"{event.name} is full, so there is nothing to register for. I can put you on the waitlist instead.")
    if registration_service.is_registered(student.student_id, event.id):
        raise ActionError(f"You're already registered for {event.name}.")
    return Prepared(
        title=f"Register for {event.name}",
        lines=[
            ConfirmationLine(label="Event", value=event.name),
            ConfirmationLine(label="When", value=f"{event.date} at {event.time}"),
            ConfirmationLine(label="Where", value=event.venue),
            ConfirmationLine(label="Student", value=student.student_id),
        ],
        params={"event_id": event.id},
    )


def execute(params: dict, student: CurrentStudent) -> Done:
    # create_registration checks everything again (seats, duplicates): time has passed.
    result = registration_service.create_registration(student.student_id, params["event_id"])
    if not result["success"]:
        raise ActionError(result["error"])
    event = event_service.get_event(params["event_id"])
    return Done(
        message=f"You're registered for {event.name}.",
        details={"Registration ID": result["registration_id"]},
    )


SPEC = ActionSpec(name=NAME, schema=SCHEMA, prepare=prepare, execute=execute)

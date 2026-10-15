from app.actions.base import ActionError, ActionSpec, Done, Prepared, text_arg
from app.actions.campus import _schema
from app.models.actions import ConfirmationLine
from app.models.auth import CurrentStudent
from app.services import engagement_service


def _event_lines(event) -> list[ConfirmationLine]:
    return [
        ConfirmationLine(label="Event", value=event.name),
        ConfirmationLine(label="When", value=f"{event.date} at {event.time}"),
        ConfirmationLine(label="Where", value=event.venue),
    ]


def _event_id(args: dict) -> str:
    return text_arg(args, "event_id", "event id", 1, 64)


# --- cancel a registration

def _prepare_cancel(args: dict, student: CurrentStudent) -> Prepared:
    try:
        event, waiting = engagement_service.check_cancellation(student.student_id, _event_id(args))
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    lines = _event_lines(event)
    if waiting:
        lines.append(ConfirmationLine(label="Note", value=f"Your seat goes to the first of {waiting} students on the waitlist"))
    return Prepared(title=f"Cancel your registration for {event.name}", lines=lines, params={"event_id": event.id})


def _execute_cancel(params: dict, student: CurrentStudent) -> Done:
    try:
        engagement_service.cancel_registration(student.student_id, params["event_id"])
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    return Done(message="Your registration is cancelled and your seat has been released.")


CANCEL_REGISTRATION = ActionSpec(
    name="cancel_event_registration",
    schema=_schema(
        "cancel_event_registration",
        "Cancel the signed-in student's registration for an event that has not started. Get the event id from get_my_registrations.",
        {"event_id": {"type": "string"}},
        ["event_id"],
    ),
    prepare=_prepare_cancel,
    execute=_execute_cancel,
)


# --- join the waitlist

def _prepare_waitlist(args: dict, student: CurrentStudent) -> Prepared:
    try:
        event, position = engagement_service.check_waitlist(student.student_id, _event_id(args))
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    lines = _event_lines(event) + [
        ConfirmationLine(label="Your place", value=str(position)),
        ConfirmationLine(label="Note", value="If a seat opens you are registered automatically"),
    ]
    return Prepared(title=f"Join the waitlist for {event.name}", lines=lines, params={"event_id": event.id})


def _execute_waitlist(params: dict, student: CurrentStudent) -> Done:
    try:
        position = engagement_service.join_waitlist(student.student_id, params["event_id"])
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    return Done(message=f"You're on the waitlist at place {position}.", details={"Waitlist place": str(position)})


JOIN_WAITLIST = ActionSpec(
    name="join_event_waitlist",
    schema=_schema(
        "join_event_waitlist",
        "Put the signed-in student on the waitlist of a full event. If a seat opens they are registered automatically.",
        {"event_id": {"type": "string"}},
        ["event_id"],
    ),
    prepare=_prepare_waitlist,
    execute=_execute_waitlist,
)


# --- feedback

def _feedback_args(args: dict) -> tuple[str, int, str | None]:
    event_id = _event_id(args)
    rating = args.get("rating")
    if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ActionError("The rating must be a whole number from 1 (poor) to 5 (excellent).")
    comments = args.get("comments")
    if comments is not None:
        if not isinstance(comments, str) or len(comments.strip()) > engagement_service.MAX_COMMENT_CHARS:
            raise ActionError(f"Comments can be up to {engagement_service.MAX_COMMENT_CHARS} characters.")
        comments = comments.strip() or None
    return event_id, rating, comments


def _prepare_feedback(args: dict, student: CurrentStudent) -> Prepared:
    event_id, rating, comments = _feedback_args(args)
    try:
        event = engagement_service.check_feedback(student.student_id, event_id)
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    lines = [ConfirmationLine(label="Event", value=event.name), ConfirmationLine(label="Rating", value=f"{rating} out of 5")]
    if comments:
        lines.append(ConfirmationLine(label="Comments", value=comments if len(comments) <= 160 else comments[:157] + "..."))
    return Prepared(title=f"Send feedback on {event.name}", lines=lines, params={"event_id": event.id, "rating": rating, "comments": comments})


def _execute_feedback(params: dict, student: CurrentStudent) -> Done:
    try:
        engagement_service.submit_feedback(student.student_id, params["event_id"], params["rating"], params["comments"])
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    return Done(message="Thank you, your feedback has been recorded.")


SUBMIT_FEEDBACK = ActionSpec(
    name="submit_event_feedback",
    schema=_schema(
        "submit_event_feedback",
        "Send the signed-in student's feedback on an event they attended (registered for, and which has started). One per event.",
        {
            "event_id": {"type": "string"},
            "rating": {"type": "integer", "description": "1 (poor) to 5 (excellent)."},
            "comments": {"type": "string", "description": "Optional comments in the student's words."},
        },
        ["event_id", "rating"],
    ),
    prepare=_prepare_feedback,
    execute=_execute_feedback,
)

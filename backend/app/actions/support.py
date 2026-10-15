
from app.actions.base import ActionError, ActionSpec, Done, Prepared, text_arg
from app.actions.campus import _schema
from app.models.actions import ConfirmationLine
from app.models.auth import CurrentStudent
from app.services import support_service


def _prepare_grievance(args: dict, student: CurrentStudent) -> Prepared:
    category = str(args.get("category", "")).strip().lower()
    description = text_arg(args, "description", "description of the grievance", 20, 2000)
    blocked = support_service.screen_grievance(category, description)
    if blocked:
        raise ActionError(blocked)
    if category not in support_service.GRIEVANCE_CATEGORIES:
        raise ActionError("The category must be one of: " + ", ".join(support_service.GRIEVANCE_CATEGORIES) + ".")
    return Prepared(
        title="Submit a grievance",
        lines=[
            ConfirmationLine(label="Category", value=category),
            ConfirmationLine(label="Details", value=description if len(description) <= 200 else description[:197] + "..."),
            ConfirmationLine(label="Next", value="Acknowledged within three working days; outcome generally within four weeks"),
        ],
        params={"category": category, "description": description},
    )


def _execute_grievance(params: dict, student: CurrentStudent) -> Done:
    ref = support_service.create_ticket(student.student_id, params["category"], params["description"])
    return Done(
        message="Your grievance has been submitted to the General Grievance Redressal Committee.",
        details={"Ticket": ref},
    )


CREATE_GRIEVANCE = ActionSpec(
    name="create_grievance_ticket",
    schema=_schema(
        "create_grievance_ticket",
        "Raise a formal grievance for the signed-in student with the General Grievance Redressal Committee. Never for "
        "ragging, harassment, safety or grade disputes: those go to other bodies and this will refuse them.",
        {
            "category": {"type": "string", "enum": list(support_service.GRIEVANCE_CATEGORIES)},
            "description": {"type": "string", "description": "What the grievance is, in the student's own words."},
        },
        ["category", "description"],
    ),
    prepare=_prepare_grievance,
    execute=_execute_grievance,
)


def _prepare_counselling(args: dict, student: CurrentStudent) -> Prepared:
    try:
        slot = support_service.check_counselling_booking(student.student_id, args.get("slot_id"))
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    return Prepared(
        title="Book a counselling appointment",
        lines=[
            ConfirmationLine(label="Date", value=slot.date),
            ConfirmationLine(label="Time", value=f"{slot.start}-{slot.end}"),
            ConfirmationLine(label="Where", value="Student Counselling Centre, first floor, Student Activity Centre"),
            ConfirmationLine(label="Privacy", value="Confidential, one-to-one, free"),
        ],
        params={"slot_id": slot.id},
    )


def _execute_counselling(params: dict, student: CurrentStudent) -> Done:
    try:
        slot = support_service.book_counselling(student.student_id, params["slot_id"])
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    return Done(message=f"Your appointment is booked for {slot.date} at {slot.start}.", details={"Slot": str(slot.id)})


BOOK_COUNSELLING = ActionSpec(
    name="book_counselling_appointment",
    schema=_schema(
        "book_counselling_appointment",
        "Book a Student Counselling Centre appointment for the signed-in student, using a slot_id from get_counselling_slots.",
        {"slot_id": {"type": "integer"}},
        ["slot_id"],
    ),
    prepare=_prepare_counselling,
    execute=_execute_counselling,
)

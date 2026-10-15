from app.actions.base import ActionError, ActionSpec, Done, Prepared, text_arg
from app.models.actions import ConfirmationLine
from app.models.auth import CurrentStudent
from app.services import campus_service, library_service, study_room_service


def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description + " This does NOT complete it: it shows the student a confirmation card, "
            "and nothing happens unless they approve it.",
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


# --- reserve a library book

def _prepare_reservation(args: dict, student: CurrentStudent) -> Prepared:
    book_id = text_arg(args, "book_id", "book id from the availability check", 1, 10).upper()
    try:
        book, summary = library_service.check_reservation(student.student_id, book_id)
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    return Prepared(
        title=f"Put a hold on {book.title}",
        lines=[
            ConfirmationLine(label="Book", value=book.title),
            ConfirmationLine(label="Author", value=book.author),
            ConfirmationLine(label="Due back", value=summary.get("earliest_due_back", "unknown")),
            ConfirmationLine(label="Your place", value=str(summary["holds_waiting"] + 1)),
        ],
        params={"book_id": book.book_id},
    )


def _execute_reservation(params: dict, student: CurrentStudent) -> Done:
    try:
        place = library_service.reserve(student.student_id, params["book_id"])
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    return Done(message=f"You're in the queue for this book, at place {place}.", details={"Queue place": str(place)})


RESERVE_BOOK = ActionSpec(
    name="reserve_library_book",
    schema=_schema(
        "reserve_library_book",
        "Put the signed-in student on the waiting list for a book that has no copy on the shelf. Use the book_id "
        "from check_library_availability.",
        {"book_id": {"type": "string", "description": "The catalogue id, e.g. 'BK-0001'."}},
        ["book_id"],
    ),
    prepare=_prepare_reservation,
    execute=_execute_reservation,
)


# --- book a study room

def _prepare_room(args: dict, student: CurrentStudent) -> Prepared:
    room_id = text_arg(args, "room_id", "room id", 1, 10)
    day = text_arg(args, "date", "date", 1, 20)
    slot = text_arg(args, "time_slot", "time slot", 4, 20)
    try:
        room, when, start = study_room_service.check_booking(room_id, day, slot)
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    end = f"{int(start[:2]) + 2:02d}:00"
    return Prepared(
        title=f"Book {room.name}",
        lines=[
            ConfirmationLine(label="Room", value=f"{room.name} (seats {room.capacity}), second floor of the library"),
            ConfirmationLine(label="Date", value=when.isoformat()),
            ConfirmationLine(label="Time", value=f"{start}-{end}"),
        ],
        params={"room_id": room.room_id, "date": when.isoformat(), "time_slot": start},
    )


def _execute_room(params: dict, student: CurrentStudent) -> Done:
    try:
        booking = study_room_service.book(student.student_id, params["room_id"], params["date"], params["time_slot"])
    except ValueError as exc:
        raise ActionError(str(exc)) from None
    return Done(
        message=f"{params['room_id']} is yours on {booking.date} from {booking.start} to {booking.end}.",
        details={"Booking": f"RB-{booking.id:05d}"},
    )


BOOK_ROOM = ActionSpec(
    name="book_study_room",
    schema=_schema(
        "book_study_room",
        "Book a library discussion room for the signed-in student for a two-hour block. Use room ids and free "
        "slots from check_study_room_availability.",
        {
            "room_id": {"type": "string", "description": "e.g. 'DR-4'."},
            "date": {"type": "string", "description": "YYYY-MM-DD, 'today' or 'tomorrow'."},
            "time_slot": {"type": "string", "description": "The block's start time such as '14:00' or '14:00-16:00'."},
        },
        ["room_id", "date", "time_slot"],
    ),
    prepare=_prepare_room,
    execute=_execute_room,
)


# --- report a maintenance problem

def _prepare_maintenance(args: dict, student: CurrentStudent) -> Prepared:
    location = text_arg(args, "location", "location", 3, 200)
    description = text_arg(args, "description", "description of the problem", 10, 1000)
    category = str(args.get("category", "")).strip().lower()
    if category not in campus_service.MAINTENANCE_CATEGORIES:
        raise ActionError("The category must be one of: " + ", ".join(campus_service.MAINTENANCE_CATEGORIES) + ".")
    if campus_service.recent_maintenance_count(student.student_id) >= campus_service.MAX_MAINTENANCE_PER_DAY:
        raise ActionError("You have already sent several maintenance requests today. Please wait before sending more.")
    return Prepared(
        title="Report a maintenance problem",
        lines=[
            ConfirmationLine(label="Where", value=location),
            ConfirmationLine(label="Type", value=category),
            ConfirmationLine(label="Problem", value=description if len(description) <= 160 else description[:157] + "..."),
        ],
        params={"location": location, "category": category, "description": description},
    )


def _execute_maintenance(params: dict, student: CurrentStudent) -> Done:
    reference = campus_service.add_maintenance_request(student.student_id, params["location"], params["category"], params["description"])
    return Done(
        message="Your request has been recorded for Facilities and Estate Management.",
        details={"Reference": reference},
    )


REPORT_MAINTENANCE = ActionSpec(
    name="report_maintenance_issue",
    schema=_schema(
        "report_maintenance_issue",
        "Report a broken fixture, electrical fault, plumbing problem or similar on campus for the signed-in student.",
        {
            "location": {"type": "string", "description": "Where the problem is, e.g. 'Main Academic Block, Room 214'."},
            "category": {"type": "string", "enum": list(campus_service.MAINTENANCE_CATEGORIES)},
            "description": {"type": "string", "description": "What is wrong."},
        },
        ["location", "category", "description"],
    ),
    prepare=_prepare_maintenance,
    execute=_execute_maintenance,
)


# --- hand in a found item

def _prepare_lost_item(args: dict, student: CurrentStudent) -> Prepared:
    description = text_arg(args, "description", "description of the item", 5, 300)
    location = text_arg(args, "location_found", "place it was found", 3, 200)
    return Prepared(
        title="Add a found item to the lost and found list",
        lines=[ConfirmationLine(label="Item", value=description), ConfirmationLine(label="Found at", value=location)],
        params={"description": description, "location_found": location},
    )


def _execute_lost_item(params: dict, student: CurrentStudent) -> Done:
    campus_service.add_lost_item(student.student_id, params["description"], params["location_found"])
    return Done(
        message="It is on the lost and found list. Handing the item in at the Student Services Desk helps its owner find it."
    )


SUBMIT_LOST_ITEM = ActionSpec(
    name="submit_lost_item",
    schema=_schema(
        "submit_lost_item",
        "Add an item the student found to the lost and found list.",
        {
            "description": {"type": "string", "description": "What the item is."},
            "location_found": {"type": "string", "description": "Where it was found."},
        },
        ["description", "location_found"],
    ),
    prepare=_prepare_lost_item,
    execute=_execute_lost_item,
)

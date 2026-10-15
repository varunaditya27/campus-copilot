from app.actions.registry import ACTION_SCHEMAS
from app.tools.academic import (
    get_attendance_report,
    get_cgpa,
    get_course_info,
    get_elective_options,
    get_exam_schedule,
    get_faculty_profile,
    get_fee_dues,
    get_student_timetable,
)
from app.tools.attendance import calculate_attendance
from app.tools.operations import (
    check_library_availability,
    check_placement_eligibility,
    check_study_room_availability,
    get_bus_schedule,
    get_canteen_menu,
    get_counselling_slots,
    get_grievance_status,
    get_lost_and_found,
    get_placement_drives,
)
from app.tools.events import check_event_availability, search_events

def _tool(name: str, description: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    parameters: dict = {"type": "object", "properties": properties or {}}
    if required:
        parameters["required"] = required
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


_DAY = {"type": "string", "description": "'today', 'tomorrow' or a weekday such as 'Monday'. Omit for today."}

OPERATIONS_SCHEMAS = [
    _tool("check_library_availability", "Look up a book by title, author or ISBN in the library catalogue: whether a copy is on the shelf, where, and if not when one is due back. Always do this before reserving a book.",
          {"query": {"type": "string", "description": "Title, author or ISBN words."}}, ["query"]),
    _tool("get_canteen_menu", "Get the Central Cafeteria menu with prices for a day (today by default), by meal with serving hours.", {"day": _DAY}),
    _tool("get_bus_schedule", "Get campus shuttle routes (A, B, C and the Saturday town shuttle): stops, today's service and the next departures.",
          {"route": {"type": "string", "description": "A route letter or name. Omit for all routes."}}),
    _tool("get_lost_and_found", "Search the lost and found list for an item by a word such as 'umbrella' or 'keys'.",
          {"keyword": {"type": "string"}}, ["keyword"]),
    _tool("check_study_room_availability", "List the library discussion rooms (seating four to eight) with their free two-hour slots on a date, up to three days ahead. Always do this before booking a room.",
          {"day": {"type": "string", "description": "YYYY-MM-DD, 'today' or 'tomorrow'. Omit for today."}, "min_capacity": {"type": "integer", "description": "Smallest group size the room must seat."}}),
    _tool("get_grievance_status", "Get the signed-in student's own grievance tickets, or one by its number, with status and expected dates.",
          {"ticket_id": {"type": "string", "description": "A ticket number such as 'GR-00012'. Omit to list the student's tickets."}}),
    _tool("get_counselling_slots", "List free Student Counselling Centre appointment slots and the signed-in student's own upcoming appointment, if any."),
    _tool("get_placement_drives", "List upcoming campus placement drives with dates, registration deadlines and criteria (minimum CGPA, backlogs, departments).",
          {"company": {"type": "string"}, "from_date": {"type": "string", "description": "YYYY-MM-DD"}, "to_date": {"type": "string", "description": "YYYY-MM-DD"}}),
    _tool("check_placement_eligibility", "Check whether the signed-in student meets a placement drive's criteria, criterion by criterion.",
          {"drive": {"type": "string", "description": "A drive id such as 'PD-003' or a company name."}}, ["drive"]),
]

# Groq's native tool-calling format: a list of {"type": "function", "function": {...}}
# definitions, matching the OpenAI function-calling schema.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": "Search campus events by keyword, topic, or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords to search for, e.g. 'AI' or 'cybersecurity'.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_event_availability",
            "description": "Check remaining seats for a specific campus event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event's id, e.g. 'evt_ai_001'.",
                    }
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_attendance",
            "description": "Calculate an exact attendance percentage from classes attended and total classes held.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attended": {"type": "integer"},
                    "total": {"type": "integer"},
                },
                "required": ["attended", "total"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attendance_report",
            "description": (
                "Get the signed-in student's own attendance this semester, subject by "
                "subject, with which subjects are below the 75% required and how many "
                "classes they would need to attend to reach it. Use this instead of "
                "guessing when they ask about their attendance."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cgpa",
            "description": (
                "Get the signed-in student's own SGPA for each completed semester, their "
                "CGPA, and any backlogs, computed from their results. Use this instead of "
                "guessing when they ask about their grades or CGPA."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_student_timetable",
            "description": "Get the signed-in student's own class timetable for one day (today by default, or tomorrow, or a weekday name) or for the whole week: times, courses and rooms. Use this when they ask what classes they have.",
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "'today', 'tomorrow', a weekday such as 'Monday', or 'week'. Omit for today."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_exam_schedule",
            "description": "Get the signed-in student's own exam dates, times and venues: internal tests, practicals and the end-semester exams, each marked upcoming or past. Defaults to their current semester.",
            "parameters": {
                "type": "object",
                "properties": {
                    "semester": {
                        "type": "integer",
                        "description": "Semester number 1-8. Omit for the current semester."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_elective_options",
            "description": "List the electives offered to the signed-in student's department in a semester, marking the ones they are taking. Defaults to their current semester.",
            "parameters": {
                "type": "object",
                "properties": {
                    "semester": {
                        "type": "integer",
                        "description": "Semester number 1-8. Omit for the current semester."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fee_dues",
            "description": "Get the signed-in student's own fees: what is paid and outstanding for each term, due dates, and any late fee. Use this instead of guessing when they ask about fees or payment deadlines.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_course_info",
            "description": "Look up a course by its code (for example 'IS501'): name, credits, semester, instructor and weekly hours. Not about any particular student.",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_code": {
                        "type": "string",
                        "description": "The course code, e.g. 'IS501'."
                    }
                },
                "required": [
                    "course_code"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_faculty_profile",
            "description": "Look up a faculty member by name or faculty id: designation, department, specialisation, office, office hours, email and the courses they teach.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The faculty member's name (a surname alone may match several) or id such as 'FAC-IS-04'."
                    }
                },
                "required": [
                    "query"
                ]
            }
        }
    },
    *OPERATIONS_SCHEMAS,
    *ACTION_SCHEMAS,
]

# Only tools that are safe to auto-execute go here. register_for_event is
# intentionally absent: it mutates data, so the model's call to it is
# intercepted by the agent loop and turned into a confirmation prompt
# instead of being run automatically. See agent/agent.py.
TOOL_FUNCTIONS = {
    "search_events": search_events,
    "check_event_availability": check_event_availability,
    "calculate_attendance": calculate_attendance,
    "get_attendance_report": get_attendance_report,
    "get_cgpa": get_cgpa,
    "get_student_timetable": get_student_timetable,
    "get_exam_schedule": get_exam_schedule,
    "get_elective_options": get_elective_options,
    "get_fee_dues": get_fee_dues,
    "get_course_info": get_course_info,
    "get_faculty_profile": get_faculty_profile,
    "check_library_availability": check_library_availability,
    "get_canteen_menu": get_canteen_menu,
    "get_bus_schedule": get_bus_schedule,
    "get_lost_and_found": get_lost_and_found,
    "check_study_room_availability": check_study_room_availability,
    "get_grievance_status": get_grievance_status,
    "get_counselling_slots": get_counselling_slots,
    "get_placement_drives": get_placement_drives,
    "check_placement_eligibility": check_placement_eligibility,
}

# Tools about the signed-in student. The agent supplies their student id from the
# login; any student id the model puts in the arguments is discarded, so the model
# cannot be talked into looking up someone else.
STUDENT_TOOLS = frozenset(
    {
        "get_attendance_report",
        "get_cgpa",
        "get_student_timetable",
        "get_exam_schedule",
        "get_elective_options",
        "get_fee_dues",
        "get_grievance_status",
        "get_counselling_slots",
        "check_placement_eligibility",
    }
)

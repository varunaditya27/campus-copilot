from app.actions.registry import ACTION_SCHEMAS
from app.tools.academic import get_attendance_report, get_cgpa
from app.tools.attendance import calculate_attendance
from app.tools.events import check_event_availability, search_events

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
}

# Tools about the signed-in student. The agent supplies their student id from the
# login; any student id the model puts in the arguments is discarded, so the model
# cannot be talked into looking up someone else.
STUDENT_TOOLS = frozenset({"get_attendance_report", "get_cgpa"})

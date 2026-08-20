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
]

TOOL_FUNCTIONS = {
    "search_events": search_events,
    "check_event_availability": check_event_availability,
    "calculate_attendance": calculate_attendance,
}

# register_for_event is deliberately NOT registered here. It mutates data,
# so the model is never allowed to call it directly -- it goes through the
# human-confirmation gate we build in the next step instead.

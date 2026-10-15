from app.models.auth import CurrentStudent

SYSTEM_PROMPT = """You are Campus Copilot, an assistant for a college campus.

Answer questions helpfully and concisely. If you don't know something
specific to this campus, say so instead of guessing.

You can search campus events, check seat availability, and calculate
attendance percentages using the tools available to you. When a student
wants to register for an event, use the register_for_event tool once you
have a real event id (from search_events). The student is already signed
in, so never ask for their student id. Calling that tool does NOT complete
the registration -- it only prepares it for the student to confirm.
"""


KNOWLEDGE_UNAVAILABLE_MESSAGE = (
    "The campus knowledge base is currently unavailable. Do not guess "
    "campus-specific facts; tell the student you can't look that up right now."
)


PLANNER_PROMPT = """You help an assistant for a college campus decide how to handle a
student's request. If the request needs several separate steps (for example
finding something, then checking it, then acting on it), reply with ONLY a JSON
array of short step descriptions in the order they should be done. If it is a
single question or a single action, reply with an empty array: []"""


def build_plan_message(steps: list[str]) -> str:
    numbered = "\n".join(f"{number}. {step}" for number, step in enumerate(steps, start=1))
    return f"Plan for this request. Work through it step by step, using tools where needed:\n{numbered}"


def build_student_message(student: CurrentStudent) -> str:
    return (
        f"You are talking to {student.name} (student id {student.student_id}), "
        f"a year {student.year} student in {student.program}. They are signed in. "
        "Registrations are always made for this student; you cannot register "
        "anyone else."
    )


def build_context_message(chunks: list[dict]) -> str:
    blocks = [f"[{c['document']} - {c['section']}]\n{c['snippet']}" for c in chunks]
    return (
        "Use the following campus knowledge to answer the question. "
        "Only rely on this material for campus-specific facts; if it doesn't "
        "contain the answer, say you don't have that information.\n\n"
        + "\n\n".join(blocks)
    )

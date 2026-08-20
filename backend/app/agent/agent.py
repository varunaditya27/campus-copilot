import json

from app.agent.prompts import SYSTEM_PROMPT, build_context_message
from app.agent.tool_registry import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.config import GROQ_MODEL
from app.core.groq_client import get_groq_client
from app.models.chat import (
    ChatHistoryItem,
    ChatResponse,
    ConfirmationEvent,
    RegistrationConfirmation,
    Source,
    ToolActivityEntry,
)
from app.rag.retriever import retrieve
from app.services import event_service

MAX_TOOL_ROUNDS = 4

TOOL_LABELS = {
    "search_events": "Searching campus events",
    "check_event_availability": "Checking event availability",
    "calculate_attendance": "Calculating attendance",
}


def _summarize(tool: str, result: dict) -> str:
    if "error" in result:
        return result["error"]
    if tool == "search_events":
        return f"Found {len(result)} matching events"
    if tool == "check_event_availability":
        return f"{result['remaining_seats']} seats available" if result["available"] else "No seats available"
    if tool == "calculate_attendance":
        return f"{result['percentage']}% attendance"
    return "Done"


def _confirmation_for(args: dict) -> RegistrationConfirmation | None:
    event = event_service.get_event(args.get("event_id", ""))
    student_id = args.get("student_id")
    if event is None or not student_id:
        return None
    return RegistrationConfirmation(
        event=ConfirmationEvent(
            id=event.id, name=event.name, date=event.date, time=event.time, venue=event.venue
        ),
        studentId=student_id,
    )


def run_agent(message: str, history: list[ChatHistoryItem]) -> ChatResponse:
    chunks = retrieve(message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": h.role, "content": h.content} for h in history]
    if chunks:
        messages.append({"role": "system", "content": build_context_message(chunks)})
    messages.append({"role": "user", "content": message})

    client = get_groq_client()
    tool_activity: list[ToolActivityEntry] = []
    confirmation: RegistrationConfirmation | None = None

    for _ in range(MAX_TOOL_ROUNDS):
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        reply_message = completion.choices[0].message

        if not reply_message.tool_calls:
            reply = reply_message.content
            break

        register_call = next(
            (tc for tc in reply_message.tool_calls if tc.function.name == "register_for_event"),
            None,
        )
        if register_call is not None:
            args = json.loads(register_call.function.arguments)
            confirmation = _confirmation_for(args)
            reply = (
                f"I've prepared a registration for {confirmation.event.name}. "
                "Please confirm below to complete it."
                if confirmation
                else "I couldn't find that event to register you for -- could you "
                "confirm the event and your student ID?"
            )
            break

        messages.append(
            {
                "role": "assistant",
                "content": reply_message.content,
                "tool_calls": [tc.model_dump() for tc in reply_message.tool_calls],
            }
        )

        for tool_call in reply_message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            try:
                result = TOOL_FUNCTIONS[name](**args)
                status = "done"
            except Exception as exc:
                result = {"error": str(exc)}
                status = "error"

            tool_activity.append(
                ToolActivityEntry(
                    id=tool_call.id,
                    tool=name,
                    label=TOOL_LABELS.get(name, name),
                    status=status,
                    resultSummary=_summarize(name, result),
                )
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": name,
                    "content": json.dumps(result),
                }
            )
    else:
        reply = "I wasn't able to finish that request in a reasonable number of steps."

    sources = [
        Source(document=c["document"], section=c["section"], snippet=c["snippet"])
        for c in chunks
    ]

    return ChatResponse(
        reply=reply,
        sources=sources,
        toolActivity=tool_activity or None,
        confirmation=confirmation,
    )

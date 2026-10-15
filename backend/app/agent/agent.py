import json
from collections.abc import Iterator

from groq import APIError, APIStatusError, BadRequestError, RateLimitError
from pydantic import ValidationError

from app.agent.prompts import (
    KNOWLEDGE_UNAVAILABLE_MESSAGE,
    SYSTEM_PROMPT,
    build_context_message,
    build_student_message,
)
from app.agent.tool_registry import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.config import GROQ_MODEL
from app.core.errors import AppError
from app.core.groq_client import get_groq_client
from app.models.chat import (
    ChatHistoryItem,
    ChatResponse,
    ConfirmationEvent,
    RegistrationConfirmation,
    Source,
    ToolActivityEntry,
)
from app.models.auth import CurrentStudent
from app.rag.retriever import KnowledgeBaseNotFound, retrieve
from app.services import event_service

MAX_TOOL_ROUNDS = 4

# Groq documents 413 for an oversized request but no specific code for an
# over-long prompt, so a 400 is matched by its message wording as well.
_CONTEXT_TOO_LONG_HINTS = ("context length", "reduce the length", "too long")

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


def _parse_arguments(raw: str) -> dict | None:
    try:
        args = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return args if isinstance(args, dict) else None


def _describe_validation_error(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}" for e in exc.errors()
    )


def _run_tool(name: str, raw_arguments: str) -> tuple[dict | list, str]:
    args = _parse_arguments(raw_arguments)
    if args is None:
        return {"error": "Tool arguments were not a valid JSON object"}, "error"
    try:
        return TOOL_FUNCTIONS[name](**args), "done"
    except ValidationError as exc:
        return {"error": _describe_validation_error(exc)}, "error"
    except Exception as exc:
        return {"error": str(exc)}, "error"


def _to_app_error(exc: APIError) -> AppError:
    if isinstance(exc, RateLimitError):
        return AppError(
            429, "rate_limited", "The AI service is busy right now. Please try again in a moment."
        )
    too_long = (isinstance(exc, APIStatusError) and exc.status_code == 413) or (
        isinstance(exc, BadRequestError)
        and any(hint in exc.message.lower() for hint in _CONTEXT_TOO_LONG_HINTS)
    )
    if too_long:
        return AppError(
            413, "context_too_long", "This conversation is too long. Please start a new chat."
        )
    return AppError(
        502, "llm_unavailable", "The AI service is unavailable right now. Please try again shortly."
    )


def _event(kind: str, **payload) -> dict:
    return {"type": kind, "payload": payload}


def _stream_completion(client, messages: list[dict]):
    """Stream one model round.

    Yields a token event for each piece of text as it arrives. The model's
    tool calls arrive as fragments (an id and name first, then the JSON
    arguments in pieces), so they are reassembled by index. Returns the full
    text and the list of complete tool calls.
    """
    text_parts: list[str] = []
    calls: dict[int, dict] = {}
    try:
        stream = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                text_parts.append(delta.content)
                yield _event("token", text=delta.content)
            for part in delta.tool_calls or []:
                call = calls.setdefault(part.index, {"id": None, "name": "", "arguments": ""})
                if part.id:
                    call["id"] = part.id
                if part.function:
                    if part.function.name:
                        call["name"] = part.function.name
                    if part.function.arguments:
                        call["arguments"] += part.function.arguments
    except APIError as exc:
        raise _to_app_error(exc) from exc

    tool_calls = [
        {**calls[index], "id": calls[index]["id"] or f"call_{index}"} for index in sorted(calls)
    ]
    return "".join(text_parts), tool_calls


def _confirmation_for(args: dict, student: CurrentStudent) -> RegistrationConfirmation | None:
    event = event_service.get_event(args.get("event_id", ""))
    if event is None:
        return None
    return RegistrationConfirmation(
        event=ConfirmationEvent(
            id=event.id, name=event.name, date=event.date, time=event.time, venue=event.venue
        ),
        studentId=student.student_id,
    )


def run_agent_stream(
    message: str, history: list[ChatHistoryItem], student: CurrentStudent
) -> Iterator[dict]:
    """Run the agent loop for a signed-in student, yielding typed events as it goes.

    Event types: rag_context, token, reset (discard the text streamed so far,
    because the model is about to call a tool), tool_start, tool_done, and
    finally done, whose payload is the complete ChatResponse. Failures raise
    AppError.
    """
    knowledge_unavailable = False
    try:
        chunks = retrieve(message)
    except KnowledgeBaseNotFound:
        chunks = []
        knowledge_unavailable = True

    sources = [
        Source(document=c["document"], section=c["section"], snippet=c["snippet"])
        for c in chunks
    ]
    yield _event("rag_context", sources=[s.model_dump() for s in sources])

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_student_message(student)},
    ]
    messages += [{"role": h.role, "content": h.content} for h in history]
    if chunks:
        messages.append({"role": "system", "content": build_context_message(chunks)})
    elif knowledge_unavailable:
        messages.append({"role": "system", "content": KNOWLEDGE_UNAVAILABLE_MESSAGE})
    messages.append({"role": "user", "content": message})

    client = get_groq_client()
    tool_activity: list[ToolActivityEntry] = []
    confirmation: RegistrationConfirmation | None = None

    for _ in range(MAX_TOOL_ROUNDS):
        text, tool_calls = yield from _stream_completion(client, messages)

        if not tool_calls:
            reply = text
            break

        if text:
            yield _event("reset")

        register_call = next((c for c in tool_calls if c["name"] == "register_for_event"), None)
        if register_call is not None:
            args = _parse_arguments(register_call["arguments"]) or {}
            confirmation = _confirmation_for(args, student)
            reply = (
                f"I've prepared a registration for {confirmation.event.name}. "
                "Please confirm below to complete it."
                if confirmation
                else "I couldn't find that event to register you for -- could you "
                "confirm which event you mean?"
            )
            yield _event("token", text=reply)
            break

        messages.append(
            {
                "role": "assistant",
                "content": text or None,
                "tool_calls": [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"]},
                    }
                    for c in tool_calls
                ],
            }
        )

        for call in tool_calls:
            name = call["name"]
            label = TOOL_LABELS.get(name, name)
            yield _event("tool_start", id=call["id"], tool=name, label=label)

            result, status = _run_tool(name, call["arguments"])
            entry = ToolActivityEntry(
                id=call["id"],
                tool=name,
                label=label,
                status=status,
                resultSummary=_summarize(name, result),
            )
            tool_activity.append(entry)
            yield _event("tool_done", **entry.model_dump())
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": name,
                    "content": json.dumps(result),
                }
            )
    else:
        reply = "I wasn't able to finish that request in a reasonable number of steps."
        yield _event("token", text=reply)

    response = ChatResponse(
        reply=reply,
        sources=sources,
        toolActivity=tool_activity or None,
        confirmation=confirmation,
    )
    yield _event("done", **response.model_dump())


def run_agent(
    message: str, history: list[ChatHistoryItem], student: CurrentStudent
) -> ChatResponse:
    """The same loop without streaming: wait for the final event."""
    events = list(run_agent_stream(message, history, student))
    return ChatResponse.model_validate(events[-1]["payload"])

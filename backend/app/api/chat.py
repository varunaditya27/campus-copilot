import json

from fastapi import APIRouter

from app.agent.tool_registry import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.config import GROQ_MODEL
from app.core.constants import SYSTEM_PROMPT
from app.core.groq_client import get_groq_client
from app.models.chat import ChatRequest, ChatResponse, Source, ToolActivityEntry
from app.rag.retriever import retrieve

router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_TOOL_ROUNDS = 4

TOOL_LABELS = {
    "search_events": "Searching campus events",
    "check_event_availability": "Checking event availability",
    "calculate_attendance": "Calculating attendance",
}


def _build_context_message(chunks: list[dict]) -> str:
    blocks = [f"[{c['document']} - {c['section']}]\n{c['snippet']}" for c in chunks]
    return (
        "Use the following campus knowledge to answer the question. "
        "Only rely on this material for campus-specific facts; if it doesn't "
        "contain the answer, say you don't have that information.\n\n"
        + "\n\n".join(blocks)
    )


def _summarize(tool: str, result: dict) -> str:
    if "error" in result:
        return result["error"]
    if tool == "search_events":
        return f"Found {len(result)} matching events" if isinstance(result, list) else "No matching events"
    if tool == "check_event_availability":
        return f"{result['remaining_seats']} seats available" if result["available"] else "No seats available"
    if tool == "calculate_attendance":
        return f"{result['percentage']}% attendance"
    return "Done"


@router.post("")
def chat(request: ChatRequest) -> ChatResponse:
    chunks = retrieve(request.message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": h.role, "content": h.content} for h in request.history]
    if chunks:
        messages.append({"role": "system", "content": _build_context_message(chunks)})
    messages.append({"role": "user", "content": request.message})

    client = get_groq_client()
    tool_activity: list[ToolActivityEntry] = []

    # Bounded loop: the model can chain a few tool calls (e.g. search_events
    # then check_event_availability) before giving a final answer. `tools`
    # stays available on every round -- dropping it on a later round is what
    # caused the model to still attempt a call the API then rejected.
    for _ in range(MAX_TOOL_ROUNDS):
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        message = completion.choices[0].message

        if not message.tool_calls:
            reply = message.content
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls],
            }
        )

        for tool_call in message.tool_calls:
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
    )

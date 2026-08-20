from app.core.config import GROQ_MODEL
from app.core.groq_client import get_groq_client
from app.models.chat import ChatHistoryItem, ChatResponse

SYSTEM_PROMPT = (
    "You are Campus Copilot, a helpful general-purpose assistant. "
    "Answer questions clearly and concisely."
)


def run_agent(message: str, history: list[ChatHistoryItem]) -> ChatResponse:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": h.role, "content": h.content} for h in history]
    messages.append({"role": "user", "content": message})

    client = get_groq_client()
    completion = client.chat.completions.create(model=GROQ_MODEL, messages=messages)
    reply = completion.choices[0].message.content

    return ChatResponse(reply=reply)

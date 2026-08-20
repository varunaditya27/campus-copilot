from app.agent.prompts import SYSTEM_PROMPT, build_context_message
from app.core.config import GROQ_MODEL
from app.core.groq_client import get_groq_client
from app.models.chat import ChatHistoryItem, ChatResponse, Source
from app.rag.retriever import retrieve


def run_agent(message: str, history: list[ChatHistoryItem]) -> ChatResponse:
    chunks = retrieve(message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": h.role, "content": h.content} for h in history]
    if chunks:
        messages.append({"role": "system", "content": build_context_message(chunks)})
    messages.append({"role": "user", "content": message})

    client = get_groq_client()
    completion = client.chat.completions.create(model=GROQ_MODEL, messages=messages)
    reply = completion.choices[0].message.content

    sources = [
        Source(document=c["document"], section=c["section"], snippet=c["snippet"])
        for c in chunks
    ]

    return ChatResponse(reply=reply, sources=sources or None)

from fastapi import APIRouter

from app.core.config import GROQ_MODEL
from app.core.constants import SYSTEM_PROMPT
from app.core.groq_client import get_groq_client
from app.models.chat import ChatRequest, ChatResponse, Source
from app.rag.retriever import retrieve

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _build_context_message(chunks: list[dict]) -> str:
    blocks = [f"[{c['document']} - {c['section']}]\n{c['snippet']}" for c in chunks]
    return (
        "Use the following campus knowledge to answer the question. "
        "Only rely on this material for campus-specific facts; if it doesn't "
        "contain the answer, say you don't have that information.\n\n"
        + "\n\n".join(blocks)
    )


@router.post("")
def chat(request: ChatRequest) -> ChatResponse:
    chunks = retrieve(request.message)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": h.role, "content": h.content} for h in request.history]
    if chunks:
        messages.append({"role": "system", "content": _build_context_message(chunks)})
    messages.append({"role": "user", "content": request.message})

    completion = get_groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
    )

    sources = [
        Source(document=c["document"], section=c["section"], snippet=c["snippet"])
        for c in chunks
    ]

    return ChatResponse(reply=completion.choices[0].message.content, sources=sources)

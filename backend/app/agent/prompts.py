SYSTEM_PROMPT = """You are Campus Copilot, an assistant for a college campus.

Answer questions helpfully and concisely. If you don't know something
specific to this campus, say so instead of guessing.
"""


def build_context_message(chunks: list[dict]) -> str:
    blocks = [f"[{c['document']} - {c['section']}]\n{c['snippet']}" for c in chunks]
    return (
        "Use the following campus knowledge to answer the question. "
        "Only rely on this material for campus-specific facts; if it doesn't "
        "contain the answer, say you don't have that information.\n\n"
        + "\n\n".join(blocks)
    )

from prometheus_client import Counter, Histogram

AGENT_TOOL_ROUNDS = Counter(
    "agent_tool_rounds_total", "Rounds in which the agent ran tools (one round may run several in parallel)", ["domain"]
)
AGENT_TOOL_CALLS = Counter("agent_tool_calls_total", "Tool calls the agent made", ["tool", "status"])
AGENT_TOOL_SECONDS = Histogram(
    "agent_tool_duration_seconds", "How long one tool call took", ["tool"], buckets=(0.005, 0.02, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 15)
)
AGENT_CONFIRMATIONS = Counter("agent_confirmations_requested_total", "Actions the agent proposed for a student to approve", ["action"])

RAG_RETRIEVAL_SECONDS = Histogram(
    "rag_retrieval_latency_seconds", "How long retrieving passages took", buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
)
RAG_CHUNKS_RETURNED = Histogram(
    "rag_chunks_returned_count", "How many passages a question got (0 means nothing relevant was found)", buckets=(0, 1, 2, 3, 5, 8, 13)
)

LLM_REQUESTS = Counter("llm_requests_total", "Language model requests", ["provider", "model", "tier", "outcome"])
LLM_REQUEST_SECONDS = Histogram(
    "llm_request_duration_seconds", "How long a language model request took, until its answer was complete",
    ["provider", "model"], buckets=(0.25, 0.5, 1, 2, 4, 8, 15, 30, 60),
)
# Counted only when the service reports usage while streaming (OpenAI and Ollama do; Groq documents nothing for it).
LLM_TOKENS = Counter("llm_tokens_used_total", "Tokens reported by the language model service", ["provider", "model", "kind"])

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"

DATA_DIR = REPO_ROOT / "data"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"
# Documents added through the admin API live apart from the curated corpus in knowledge/.
UPLOAD_DIR = Path(os.getenv("KNOWLEDGE_UPLOAD_DIR", BACKEND_DIR / "knowledge_uploads"))

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{REPO_ROOT / 'backend' / 'campus.db'}")

CHROMA_DIR = Path(os.getenv("CHROMA_DIR", REPO_ROOT / "backend" / "chroma"))
KNOWLEDGE_COLLECTION = "campus_knowledge"

# Which vector database holds the knowledge base: "chroma" (the default; local
# files, or a Chroma server if CHROMA_HOST is set) or "qdrant".
VECTOR_STORE = os.getenv("VECTOR_STORE", "chroma").lower()
if VECTOR_STORE not in ("chroma", "qdrant"):
    raise RuntimeError(f"VECTOR_STORE must be 'chroma' or 'qdrant', not '{VECTOR_STORE}'.")
CHROMA_HOST = os.getenv("CHROMA_HOST", "")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

# Before answering, ask the model to break a multi-step request into steps. This
# costs an extra model call on every question and has not been shown to help
# yet, so it is off until there is an evaluation to prove it. Set to "true" to try it.
AGENT_PLANNING = os.getenv("AGENT_PLANNING", "false").lower() == "true"

# Whether a router sends each question to a specialist agent (academic, events,
# library, grievance or general) that sees only its own tools, running several in
# parallel for a question that spans domains. It costs an extra model call per
# question and has not been compared with the single agent on real traffic, so
# it is off until there is an evaluation to prove it. Set to "true" to try it.
MULTI_AGENT = os.getenv("MULTI_AGENT", "false").lower() == "true"

# How many passages the agent gets for a question.
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# Reciprocal Rank Fusion constant: higher values flatten the advantage of
# the very top ranks when merging keyword and semantic results.
RAG_RRF_K = int(os.getenv("RAG_RRF_K", "60"))

# Passages the reranker scores below this are treated as "not actually about
# this" and are not given to the model. Chosen from the evaluation set
# (python -m app.rag.evaluate): the reranker scored every on-topic question's
# best passage above -7.1 and every off-topic question's below -9.8.
# Re-check it if the reranker model or the corpus changes.
RAG_RERANK_MIN_SCORE = float(os.getenv("RAG_RERANK_MIN_SCORE", "-8.5"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

_jwt_secret = os.getenv("JWT_SECRET", "")
if not _jwt_secret:
    # A random key is safe but short-lived: every restart signs everyone out,
    # and several server processes would each have a different key.
    _jwt_secret = secrets.token_hex(32)
    logging.getLogger(__name__).warning(
        "JWT_SECRET is not set; using a temporary one. Set it in production "
        "(for example: openssl rand -hex 32)."
    )
elif len(_jwt_secret) < 32:
    raise RuntimeError("JWT_SECRET must be at least 32 characters (openssl rand -hex 32).")
JWT_SECRET = _jwt_secret
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 14

# Send the session cookie over HTTPS only. Turn on once the app is served over HTTPS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

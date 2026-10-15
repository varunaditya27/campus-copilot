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
CHROMA_COLLECTION = "campus_knowledge"

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

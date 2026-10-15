import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = REPO_ROOT / "data"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{REPO_ROOT / 'backend' / 'campus.db'}")

CHROMA_DIR = REPO_ROOT / "backend" / "chroma"
CHROMA_COLLECTION = "campus_knowledge"

# Chunks farther than this (L2 distance, all-MiniLM-L6-v2) are treated as
# "not actually about this" rather than force-fed to the model as context.
# Calibrated empirically: on-topic queries against this corpus land at
# ~0.7-1.3, off-topic queries land at ~1.8+. Re-calibrate if the embedding
# model or the corpus changes.
MAX_DISTANCE = float(os.getenv("RAG_MAX_DISTANCE", "1.5"))

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

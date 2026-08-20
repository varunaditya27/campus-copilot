import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = REPO_ROOT / "data"
KNOWLEDGE_DIR = REPO_ROOT / "knowledge"

CHROMA_DIR = REPO_ROOT / "backend" / "chroma"
CHROMA_COLLECTION = "campus_knowledge"

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

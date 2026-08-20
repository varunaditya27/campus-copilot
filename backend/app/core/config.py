from pathlib import Path

import os

from dotenv import load_dotenv

load_dotenv()

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = REPO_ROOT / "data"

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

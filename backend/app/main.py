from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.events import router as events_router
from app.core.config import CORS_ORIGINS

app = FastAPI(title="Campus Copilot API")
app.include_router(events_router)
app.include_router(chat_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}

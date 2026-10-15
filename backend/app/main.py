from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.events import router as events_router
from app.api.registration import router as registration_router
from app.core.config import CORS_ORIGINS
from app.core.errors import register_error_handlers
from app.core.origin_check import OriginCheckMiddleware

app = FastAPI(title="Campus Copilot API")
register_error_handlers(app)
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(chat_router)
app.include_router(registration_router)

# Added first so CORS (added next) wraps it: even a refusal then carries CORS headers.
app.add_middleware(OriginCheckMiddleware, allowed_origins=CORS_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}

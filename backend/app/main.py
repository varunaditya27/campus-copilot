import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.actions import router as actions_router
from app.api.admin_analytics import router as admin_analytics_router
from app.api.admin_events import router as admin_events_router
from app.api.admin_grievances import router as admin_grievances_router
from app.api.admin_knowledge import router as admin_knowledge_router
from app.api.admin_students import router as admin_students_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.events import router as events_router
from app.api.staff import router as staff_router
from app.api.students import router as students_router
from app.core.config import CORS_ORIGINS, COOKIE_SECURE, ENVIRONMENT, JWT_SECRET_IS_TEMPORARY
from app.core.errors import register_error_handlers
from app.core.origin_check import OriginCheckMiddleware
from app.db.session import engine
from app.llm import LLMConfigError, get_llm_client
from app.observability.logging import configure_logging
from app.observability.middleware import RequestLoggingMiddleware
from app.observability.sentry import init_sentry
from app.observability.tracing import setup_tracing
from app.rag import retriever
from app.security.headers import SecurityHeadersMiddleware
from app.security.limits import limiter, rate_limit_handler
from app.security.settings_check import origin_problems, production_problems
from slowapi.errors import RateLimitExceeded

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the search models and index now, in a worker thread, so the first
    # question is not slow and the server can still answer requests meanwhile.
    await run_in_threadpool(retriever.warm_up)
    try:
        client = get_llm_client()
        logger.info("Language model: %s (fast=%s, balanced=%s, best=%s)", client.provider, *(client.model_for(t) for t in ("fast", "balanced", "best")))
    except LLMConfigError as exc:
        logger.error("Language model not configured: %s", exc)  # chat will fail until this is fixed
    yield


configure_logging()
init_sentry()
_problems = production_problems(ENVIRONMENT, CORS_ORIGINS, COOKIE_SECURE, not JWT_SECRET_IS_TEMPORARY)
if _problems:
    raise RuntimeError("Not safe to run in production:\n- " + "\n- ".join(_problems))
for _problem in origin_problems(CORS_ORIGINS):
    logging.getLogger(__name__).warning("%s", _problem)
logger = logging.getLogger(__name__)

app = FastAPI(title="Campus Copilot API", lifespan=lifespan)
register_error_handlers(app)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
app.include_router(auth_router)
app.include_router(actions_router)
app.include_router(admin_students_router)
app.include_router(admin_grievances_router)
app.include_router(admin_analytics_router)
app.include_router(events_router)
app.include_router(chat_router)
app.include_router(staff_router)
app.include_router(students_router)
app.include_router(admin_events_router)
app.include_router(admin_knowledge_router)

# Added first so CORS (added next) wraps it: even a refusal then carries CORS headers.
app.add_middleware(OriginCheckMiddleware, allowed_origins=CORS_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Added last, so it wraps everything else and its request id and timing cover the whole request.
app.add_middleware(SecurityHeadersMiddleware, production=ENVIRONMENT == "production")
app.add_middleware(RequestLoggingMiddleware)
setup_tracing(app, engine)
# Prometheus metrics at /metrics: request counts and latency per route, plus the agent's own (observability/metrics.py).
# It is not served by the reverse proxy in docker-compose.prod.yml, so it is only reachable inside the network.
Instrumentator(excluded_handlers=["/metrics", "/health"]).instrument(app).expose(app, include_in_schema=False)


@app.get("/health")
def health():
    return {"status": "ok"}

from limits import parse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core import config, security
from app.observability import metrics


def client_key(request: Request) -> str:
    """Who a request counts against: the signed-in student if there is one, else the network address.

    The token is only decoded here, not trusted for anything but this count: a forged cookie cannot
    be used to dodge a limit, because it then falls back to the address."""
    token = request.cookies.get("access_token")
    user_id = security.decode_access_token(token) if token else None
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


limiter = Limiter(
    key_func=client_key,
    storage_uri=config.REDIS_URL or "memory://",
    strategy="moving-window",
    headers_enabled=False,
)


def chat_limit() -> str:
    return config.RATE_LIMIT_CHAT


def auth_limit() -> str:
    return config.RATE_LIMIT_AUTH


def allow(scope: str, key: str, limit: str | None = None) -> bool:
    """Count one use of a named allowance outside an endpoint decorator. False means it is used up."""
    return limiter.limiter.hit(parse(limit or config.RATE_LIMIT_AUTH), scope, key)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    scope = "chat" if request.url.path.startswith("/api/chat") else "auth"
    metrics.RATE_LIMITED.labels(scope).inc()
    retry_after = int(exc.limit.limit.get_expiry())
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={
            "error_code": "rate_limited",
            "message": "You are sending requests too quickly. Please wait a moment and try again.",
            "detail": {"retry_after_seconds": retry_after},
        },
    )

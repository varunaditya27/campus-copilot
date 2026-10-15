import re
import time
from uuid import uuid4

from app.observability import context
from app.observability.logging import get_logger

logger = get_logger("app.request")

_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
QUIET_PATHS = ("/health", "/metrics")


class RequestLoggingMiddleware:
    """Gives each request an id (taken from X-Request-ID if the caller sent a sensible one), returns it in the
    response, and logs one line per request with its status and duration.

    Written as plain ASGI so it does not hold back streamed replies: a server-sent stream is
    logged when its last chunk has gone out, with the time the whole stream took."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = supplied if _VALID_ID.match(supplied) else uuid4().hex
        context.start_request({"request_id": request_id})
        started = time.perf_counter()
        status = {"code": 0}
        logged = {"done": False}
        method, path = scope["method"], scope["path"]

        def log(level: str, **extra) -> None:
            if logged["done"]:
                return
            logged["done"] = True
            quiet = path in QUIET_PATHS
            getattr(logger, "debug" if quiet and level == "info" else level)(
                "request", method=method, path=path, status=status["code"],
                duration_ms=round((time.perf_counter() - started) * 1000, 1), **extra,
            )

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message = {**message, "headers": [*message.get("headers", []), (b"x-request-id", request_id.encode())]}
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                log("info")

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            status["code"] = status["code"] or 500
            log("error", error="unhandled")
            raise
        finally:
            log("info")  # a client that disconnected before the end still gets a line

from starlette.datastructures import Headers
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# What a response to this API may do in a browser: nothing but be read as data.
_API_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
_API_ONLY = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
_HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")


class SecurityHeadersMiddleware:
    """Adds browser-hardening headers to every response and, in production, insists on HTTPS.

    The application itself speaks plain HTTP to the reverse proxy (Caddy), which handles TLS. The proxy
    says what the browser used in X-Forwarded-Proto, so a request that arrived as HTTP is redirected to HTTPS.
    A request with no such header (the container's own health check, a local call) is left alone."""

    def __init__(self, app: ASGIApp, production: bool = False) -> None:
        self.app = app
        self.production = production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        if self.production and headers.get("x-forwarded-proto", "").lower() == "http":
            url = f"https://{headers.get('host', '')}{scope['path']}"
            if scope.get("query_string"):
                url += "?" + scope["query_string"].decode("latin-1")
            await RedirectResponse(url, status_code=308)(scope, receive, send)
            return

        path = scope["path"]

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                present = {name.lower() for name, _ in message.get("headers", [])}
                extra = [h for h in _API_HEADERS if h[0] not in present]
                if path.startswith("/api/") and _API_ONLY[0] not in present:
                    extra.append(_API_ONLY)
                if path.startswith("/api/auth/") and b"cache-control" not in present:
                    extra.append((b"cache-control", b"no-store"))
                if self.production and _HSTS[0] not in present:
                    extra.append(_HSTS)
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        await self.app(scope, receive, send_with_headers)

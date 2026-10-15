from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class OriginCheckMiddleware:
    """Refuse state-changing requests that a browser sent from an unknown site.

    Cookies authenticate users, so a page on another site could try to make
    the browser send a request on a user's behalf (CSRF). Browsers always send
    an Origin header on such requests, so a request whose Origin is not one of
    ours is rejected. Requests with no Origin (curl, server-to-server) are not
    browser CSRF and pass. This backs up SameSite cookies, which alone are not
    treated as enough.
    """

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed_origins = set(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in _UNSAFE_METHODS:
            origin = dict(scope["headers"]).get(b"origin")
            if origin is not None and origin.decode("latin-1") not in self.allowed_origins:
                response = JSONResponse(
                    status_code=403,
                    content={
                        "error_code": "forbidden_origin",
                        "message": "This request came from an origin that is not allowed.",
                        "detail": None,
                    },
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)

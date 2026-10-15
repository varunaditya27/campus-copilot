import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from app.core import config
from app.core.errors import AppError


def _scrub(event, hint):
    """Keep only what helps find the bug: no cookies, headers, bodies or query strings."""
    request = event.get("request")
    if request:
        for key in ("cookies", "headers", "data", "query_string"):
            request.pop(key, None)
    event.pop("user", None)
    return event


def init_sentry(dsn: str | None = None, transport=None) -> bool:
    """Report unexpected errors to Sentry, if a DSN is set. Expected failures (AppError) are not errors."""
    dsn = dsn if dsn is not None else config.SENTRY_DSN
    if not dsn:
        return False
    sentry_sdk.init(
        dsn=dsn,
        environment=config.ENVIRONMENT,
        release=config.SENTRY_RELEASE or None,
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        max_request_body_size="never",
        # The variables in each stack frame of a traceback include the request itself, with its cookies and headers.
        include_local_variables=False,
        # Our own error logs would otherwise be reported a second time, apart from the exception they describe.
        integrations=[LoggingIntegration(level=logging.INFO, event_level=None)],
        ignore_errors=[AppError],
        before_send=_scrub,
        transport=transport,
    )
    return True

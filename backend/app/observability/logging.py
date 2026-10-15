import logging
import sys

import structlog
from opentelemetry import trace

from app.core import config
from app.observability.context import request_fields

_MARK = "_campus_handler"


def _add_request_fields(logger, method, event_dict):
    for key, value in request_fields().items():
        event_dict.setdefault(key, value)
    return event_dict


def _add_trace_ids(logger, method, event_dict):
    """Tie a log line to its trace, so a slow request can be found from its logs and the other way round."""
    context = trace.get_current_span().get_span_context()
    if context.is_valid:
        event_dict["trace_id"] = format(context.trace_id, "032x")
        event_dict["span_id"] = format(context.span_id, "016x")
    return event_dict


def configure_logging(level: str | None = None, log_format: str | None = None, stream=None) -> None:
    """Send every log line, ours and the libraries', through structlog as JSON (or readable text).

    Safe to call again: it replaces the handler it added earlier and leaves any other handler alone."""
    shared = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_fields,
        _add_trace_ids,
        structlog.processors.StackInfoRenderer(),
    ]
    renderer = (
        structlog.dev.ConsoleRenderer() if (log_format or config.LOG_FORMAT) == "console" else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,  # so a later configure_logging() takes effect on loggers already made
    )
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.format_exc_info,
                renderer,
            ],
        )
    )
    setattr(handler, _MARK, True)
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not getattr(h, _MARK, False)] + [handler]
    root.setLevel(level or config.LOG_LEVEL)
    # Requests are logged by RequestLoggingMiddleware, with more than uvicorn's access line has.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None):
    return structlog.stdlib.get_logger(name)

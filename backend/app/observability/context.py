from contextvars import ContextVar

# The fields describing the request being handled (its id, who is signed in). The dictionary is
# shared, so a field set deep inside a worker thread still shows on the request's final log line.
_request_fields: ContextVar[dict | None] = ContextVar("request_fields", default=None)


def start_request(fields: dict) -> dict:
    current = dict(fields)
    _request_fields.set(current)
    return current


def request_fields() -> dict:
    return _request_fields.get() or {}


def bind(**fields) -> None:
    """Add fields to the request being handled, for example the signed-in user."""
    current = _request_fields.get()
    if current is not None:
        current.update(fields)

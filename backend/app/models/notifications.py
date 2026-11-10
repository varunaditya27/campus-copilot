from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

# The server sends a request to whatever address a browser registers, so only the browsers' own push
# services are accepted. Anything else would let a student make the server call internal addresses.
# shortcut: a short fixed list; add a host here if a browser's push service is refused.
PUSH_SERVICE_HOSTS = ("fcm.googleapis.com", "push.services.mozilla.com", "web.push.apple.com", "notify.windows.com")


def is_push_service_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    host = parts.hostname or ""
    return (
        parts.scheme == "https"
        and parts.username is None
        and parts.password is None
        and port in (None, 443)
        and any(host == allowed or host.endswith("." + allowed) for allowed in PUSH_SERVICE_HOSTS)
    )


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=256)
    auth: str = Field(min_length=1, max_length=64)


class PushSubscriptionIn(BaseModel):
    """What a browser's PushSubscription.toJSON() gives."""

    endpoint: str = Field(max_length=2048)
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def _is_a_push_service(cls, value: str) -> str:
        if not is_push_service_url(value):
            raise ValueError("must be the address of a browser push service")
        return value


class PushEndpoint(BaseModel):
    endpoint: str = Field(max_length=2048)

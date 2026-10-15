import hashlib
import hmac
import secrets

from app.core import config

PREFIX = "ccak_"


def hash_key(key: str) -> str:
    """A key is long and random, so a fast hash is enough: there is nothing to guess and nothing to stretch."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_key() -> tuple[str, str]:
    """A new key, and the digest to put in ADMIN_API_KEY_HASHES. Only the digest is kept by the server."""
    key = PREFIX + secrets.token_urlsafe(32)
    return key, hash_key(key)


def verify(key: str, hashes: list[str] | None = None) -> str | None:
    """The short id of the matching key (the start of its digest), or None. The comparison takes the
    same time whether the key is nearly right or entirely wrong."""
    digest = hash_key(key)
    match = None
    for known in config.ADMIN_API_KEY_HASHES if hashes is None else hashes:
        if hmac.compare_digest(digest, known):
            match = known[:8]
    return match

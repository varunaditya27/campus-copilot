import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import ACCESS_TOKEN_MINUTES, JWT_SECRET

# Pinned on decode, so a token cannot choose its own algorithm (for example "none").
JWT_ALGORITHM = "HS256"

_password_hash = PasswordHash.recommended()  # Argon2id
_DUMMY_HASH = _password_hash.hash("a password nobody has")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check a password. With no stored hash (unknown account) it still does
    one full Argon2 check, so the response time does not reveal whether the
    account exists."""
    matches = _password_hash.verify(password, password_hash or _DUMMY_HASH)
    return matches and password_hash is not None


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user_id),
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """The user id inside a valid, unexpired access token, or None."""
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
        if claims.get("typ") != "access":
            return None
        return int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None


def new_refresh_token() -> tuple[str, str]:
    """A fresh random refresh token and its hash. Only the hash is stored."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    # The token is 256 random bits, so a fast hash is enough here (unlike a password).
    return hashlib.sha256(raw.encode()).hexdigest()

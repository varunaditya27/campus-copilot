import base64
import json
from datetime import datetime, timedelta, timezone

import jwt

from app.core import security
from app.core.config import JWT_SECRET


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def _claims(**overrides):
    now = datetime.now(timezone.utc)
    claims = {"sub": "7", "typ": "access", "iat": now, "exp": now + timedelta(minutes=5)}
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def _sign(claims, key=JWT_SECRET, algorithm="HS256"):
    return jwt.encode(claims, key, algorithm=algorithm)


def test_password_round_trip_and_salting():
    first = security.hash_password("correct horse battery")
    second = security.hash_password("correct horse battery")

    assert first != second
    assert first.startswith("$argon2id$")
    assert security.verify_password("correct horse battery", first)
    assert not security.verify_password("wrong password", first)


def test_unknown_account_never_verifies():
    assert not security.verify_password("anything", None)
    assert not security.verify_password("a password nobody has", None)


def test_access_token_round_trip():
    assert security.decode_access_token(security.create_access_token(42)) == 42


def test_expired_token_is_rejected():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert security.decode_access_token(_sign(_claims(exp=past))) is None


def test_token_signed_with_another_key_is_rejected():
    assert security.decode_access_token(_sign(_claims(), key="x" * 40)) is None


def test_tampered_token_is_rejected():
    header, payload, signature = security.create_access_token(1).split(".")
    forged = _b64({"sub": "2", "typ": "access", "iat": 0, "exp": 9999999999})
    assert security.decode_access_token(f"{header}.{forged}.{signature}") is None


def test_unsigned_alg_none_token_is_rejected():
    token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(_claims(exp=9999999999, iat=0))}."
    assert security.decode_access_token(token) is None


def test_token_with_a_different_algorithm_is_rejected():
    assert security.decode_access_token(_sign(_claims(), key=JWT_SECRET * 2, algorithm="HS512")) is None


def test_token_without_required_claims_is_rejected():
    assert security.decode_access_token(_sign(_claims(sub=None))) is None
    assert security.decode_access_token(_sign(_claims(exp=None))) is None


def test_token_of_another_type_is_rejected():
    assert security.decode_access_token(_sign(_claims(typ="refresh"))) is None


def test_token_with_a_non_numeric_subject_is_rejected():
    assert security.decode_access_token(_sign(_claims(sub="admin"))) is None


def test_garbage_is_rejected():
    assert security.decode_access_token("not a token") is None
    assert security.decode_access_token("") is None


def test_refresh_tokens_are_random_and_only_the_hash_matches():
    raw_a, hash_a = security.new_refresh_token()
    raw_b, _ = security.new_refresh_token()

    assert raw_a != raw_b
    assert hash_a == security.hash_refresh_token(raw_a)
    assert raw_a not in hash_a
    assert len(raw_a) >= 40

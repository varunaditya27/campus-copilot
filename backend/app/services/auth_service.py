from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core import security
from app.core.config import REFRESH_TOKEN_DAYS
from app.core.errors import AppError
from app.db import session as db_session
from app.db.models import RefreshToken, Student, User
from app.models.auth import CurrentStudent

# If a just-rotated refresh token is presented again within this many seconds,
# it is most likely two tabs refreshing at once, not theft: refuse it, but
# leave the login alone.
REUSE_LEEWAY_SECONDS = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(moment: datetime) -> datetime:
    # SQLite hands back naive datetimes; everything stored here is UTC.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _not_authenticated() -> AppError:
    return AppError(401, "not_authenticated", "Please sign in again.")


def _profile(user: User, student: Student) -> CurrentStudent:
    return CurrentStudent(
        user_id=user.id,
        student_id=student.student_id,
        name=student.name,
        program=student.program,
        year=student.year,
        email=user.email,
    )


def register(student_id: str, name: str, email: str, password: str) -> int:
    """Create an account for a student on the roster. Returns the user id."""
    email = email.lower()
    with db_session.SessionLocal() as db:
        student = db.get(Student, student_id)
        if student is None or student.name.casefold().strip() != name.casefold().strip():
            raise AppError(
                400, "student_not_matched", "We couldn't match those details to a student record."
            )
        if db.scalar(select(User.id).where(User.student_id == student_id)) is not None:
            raise AppError(409, "account_exists", "An account already exists for this student.")
        if db.scalar(select(User.id).where(User.email == email)) is not None:
            raise AppError(409, "email_taken", "That email address is already registered.")

        user = User(student_id=student_id, email=email, password_hash=security.hash_password(password))
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise AppError(409, "account_exists", "An account already exists for this student.")
        return user.id


def authenticate(email: str, password: str) -> int | None:
    with db_session.SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        matches = security.verify_password(password, user.password_hash if user else None)
        return user.id if user is not None and matches and user.is_active else None


def get_current_student(user_id: int) -> CurrentStudent | None:
    with db_session.SessionLocal() as db:
        row = db.execute(
            select(User, Student)
            .join(Student, Student.student_id == User.student_id)
            .where(User.id == user_id, User.is_active)
        ).first()
        return _profile(*row) if row else None


def _store_refresh_token(db, user_id: int, family_id: UUID) -> str:
    raw, token_hash = security.new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id,
            token_hash=token_hash,
            expires_at=_now() + timedelta(days=REFRESH_TOKEN_DAYS),
        )
    )
    return raw


def start_login(user_id: int) -> tuple[str, str]:
    """Tokens for a fresh login: (access token, refresh token)."""
    with db_session.SessionLocal() as db:
        refresh = _store_refresh_token(db, user_id, uuid4())
        db.commit()
    return security.create_access_token(user_id), refresh


def _revoke_family(db, family_id: UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def refresh(raw_token: str) -> tuple[str, str]:
    """Swap a refresh token for a new access token and a new refresh token.

    The presented token stops working. Presenting one that was already used
    suggests it was stolen, so the whole login (family) is revoked.
    """
    with db_session.SessionLocal() as db:
        token = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == security.hash_refresh_token(raw_token))
        )
        if token is None:
            raise _not_authenticated()

        now = _now()
        if token.revoked_at is not None:
            if now - _aware(token.revoked_at) > timedelta(seconds=REUSE_LEEWAY_SECONDS):
                _revoke_family(db, token.family_id)
                db.commit()
            raise _not_authenticated()
        if _aware(token.expires_at) <= now:
            raise _not_authenticated()

        user = db.get(User, token.user_id)
        if user is None or not user.is_active:
            raise _not_authenticated()

        # Only one of several simultaneous requests can flip revoked_at.
        claimed = db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        if claimed.rowcount != 1:
            db.rollback()
            raise _not_authenticated()

        new_refresh = _store_refresh_token(db, user.id, token.family_id)
        db.commit()
        return security.create_access_token(user.id), new_refresh


def logout(raw_token: str | None) -> None:
    """Revoke the login that this refresh token belongs to. Safe to repeat."""
    if not raw_token:
        return
    with db_session.SessionLocal() as db:
        token = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == security.hash_refresh_token(raw_token))
        )
        if token is not None:
            _revoke_family(db, token.family_id)
            db.commit()

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import session as db_session
from app.db.models import PendingAction, UsageEvent
from app.models.chat import ChatResponse

logger = logging.getLogger(__name__)

MAX_TERMS_PER_QUESTION = 20
TOP_TERMS = 40
TOP_DOCUMENTS = 10
# A word has to appear this many times before it is shown, so a name or an id that one
# student typed once never appears on the dashboard.
MIN_TERM_COUNT = 2
SESSION_BUCKETS = ((1, 1, "1"), (2, 3, "2-3"), (4, 6, "4-6"), (7, 10**9, "7+"))

_WORD = re.compile(r"[a-z][a-z'-]{2,}")
_STOPWORDS = frozenset(
    """the and for are but not you your can will would could should may might what when where which who whom whose why how
    that this these those with from into about have has had was were been being does did doing get got give tell show let
    please need want like know there here their them they then than also just any all some more most much many very out
    off over under again too its it's i'm i've don't can't me my mine our ours his her him she hers him one two use using
    help find look able make made see said say says go going come comes new""".split()
)


def terms_of(text: str) -> list[str]:
    """The distinct meaningful words of a question: lowercase, three letters or more, common words dropped."""
    seen: list[str] = []
    for word in _WORD.findall(text.lower()):
        word = word.strip("'-")
        if len(word) >= 3 and word not in _STOPWORDS and word not in seen:
            seen.append(word)
    return seen[:MAX_TERMS_PER_QUESTION]


def record_exchange(student_id: str, session_id: str, message: str, response: ChatResponse) -> None:
    """Note that a question was answered. Never raises: analytics must not break the chat."""
    try:
        sources = response.sources or []
        with db_session.SessionLocal() as db:
            db.add(
                UsageEvent(
                    student_id=student_id,
                    session_id=str(session_id),
                    terms=terms_of(message),
                    tools=[[entry.tool, entry.status] for entry in response.toolActivity or []],
                    documents=sorted({s.document for s in sources}),
                    zero_context=not sources,
                )
            )
            db.commit()
    except Exception:
        logger.exception("Could not record usage")


def _utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _share(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def summary(days: int, now: datetime | None = None) -> dict:
    """Usage over the last `days` days (UTC), from the recorded exchanges and pending actions."""
    now = now or datetime.now(timezone.utc)
    first_day = (now - timedelta(days=days - 1)).date()
    start = datetime.combine(first_day, datetime.min.time(), tzinfo=timezone.utc)
    with db_session.SessionLocal() as db:
        events = [e for e in db.scalars(select(UsageEvent).order_by(UsageEvent.id)) if _utc(e.created_at) >= start]
        actions = [a for a in db.scalars(select(PendingAction)) if _utc(a.created_at) >= start]

    per_day: dict = {first_day + timedelta(days=i): [set(), 0] for i in range(days)}
    per_session: Counter = Counter()
    tool_counts: Counter = Counter()
    tool_errors: Counter = Counter()
    documents: Counter = Counter()
    terms: Counter = Counter()
    tool_calls = used_tools = zero_context = 0
    for event in events:
        day = per_day.get(_utc(event.created_at).date())
        if day is not None:
            day[0].add(event.student_id)
            day[1] += 1
        per_session[event.session_id] += 1
        for name, status in event.tools:
            tool_counts[name] += 1
            tool_errors[name] += status == "error"
        tool_calls += len(event.tools)
        used_tools += bool(event.tools)
        documents.update(event.documents)
        terms.update(event.terms)
        zero_context += event.zero_context

    replies = len(events)
    buckets = [
        {"label": label, "sessions": sum(1 for n in per_session.values() if low <= n <= high)} for low, high, label in SESSION_BUCKETS
    ]
    status = Counter()
    for action in actions:
        status["expired" if action.status == "pending" and _utc(action.expires_at) <= now else action.status] += 1
    accepted = status["confirmed"] + status["failed"]
    decided = accepted + status["cancelled"]
    return {
        "window_days": days,
        "from": first_day.isoformat(),
        "to": now.date().isoformat(),
        "totals": {"questions": replies, "sessions": len(per_session), "active_students": len({e.student_id for e in events})},
        "daily_active_users": [{"date": d.isoformat(), "users": len(v[0]), "questions": v[1]} for d, v in per_day.items()],
        "messages_per_session": {"average": round(replies / len(per_session), 2) if per_session else None, "buckets": buckets},
        "tool_usage": [{"tool": t, "count": c, "errors": tool_errors[t]} for t, c in tool_counts.most_common()],
        "top_documents": [{"document": d, "count": c} for d, c in documents.most_common(TOP_DOCUMENTS)],
        "top_terms": [{"term": t, "count": c} for t, c in terms.most_common() if c >= MIN_TERM_COUNT][:TOP_TERMS],
        "agent": {
            "replies": replies,
            "replies_with_tools": used_tools,
            "tool_calls": tool_calls,
            "avg_tool_calls_per_reply": round(tool_calls / replies, 2) if replies else None,
            "actions": {
                "proposed": len(actions),
                "confirmed": status["confirmed"],
                "cancelled": status["cancelled"],
                "failed": status["failed"],
                "expired": status["expired"],
                "waiting": status["pending"],
                "accept_rate": _share(accepted, decided),
                "decided": decided,
            },
        },
        "rag": {
            "replies": replies,
            "zero_context_replies": zero_context,
            "zero_context_rate": _share(zero_context, replies),
            "average_distance": None,
            "cache_hit_rate": None,
            "notes": "Retrieval distance is not recorded (the reranker's score is not kept), and there is no answer cache, so there is no hit rate.",
        },
    }

import threading
from datetime import datetime, timezone

from app.core.errors import AppError
from app.rag import retriever
from app.rag.evaluate import evaluate, load_golden

# An evaluation takes about a minute, too long to hold an HTTP request open, so
# it runs in the background and its latest outcome is kept here. This is per
# server process: with several workers, ask the same one you started it on.
_lock = threading.Lock()
_state: dict = {"state": "idle"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(k: int) -> None:
    try:
        golden = load_golden()
        shared = retriever.get_retriever()
        report = evaluate(shared.search, lambda query: shared.retrieve(query, k), golden, k=k)
        outcome = {"state": "done", "report": report}
    except Exception as exc:
        outcome = {"state": "failed", "error": f"{type(exc).__name__}: {exc}"}
    with _lock:
        _state.update(outcome, finished_at=_now())


def start(k: int = 3) -> dict:
    with _lock:
        if _state["state"] == "running":
            raise AppError(409, "eval_in_progress", "An evaluation is already running.")
        _state.clear()
        _state.update(state="running", k=k, started_at=_now())
        snapshot = dict(_state)
    threading.Thread(target=_run, args=(k,), daemon=True, name="rag-eval").start()
    return snapshot


def current() -> dict:
    with _lock:
        return dict(_state)

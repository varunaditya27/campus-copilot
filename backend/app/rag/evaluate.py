"""Measure how well retrieval finds the right passages.

Run with: python -m app.rag.evaluate [--k 3] [--log LABEL]

Each question in rag_eval/golden.json lists the facts needed to answer it. A
fact is found when a retrieved chunk comes from the right document and
contains the evidence phrase. Matching on text instead of chunk ids keeps the
dataset valid when the way documents are chunked changes.
"""

import argparse
import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import BACKEND_DIR

EVAL_DIR = BACKEND_DIR / "rag_eval"
GOLDEN_PATH = EVAL_DIR / "golden.json"
HISTORY_PATH = EVAL_DIR / "history.jsonl"

Search = Callable[[str, int], list[dict]]
Retrieve = Callable[[str], list[dict]]

# Deepest rank looked at. Hit@MAX_RANK shows whether a reranker could still find the answer.
MAX_RANK = 10


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load_golden(path: Path = GOLDEN_PATH) -> dict:
    return json.loads(path.read_text())


def fact_found(fact: list[list[str]], chunk: dict) -> bool:
    """True if the chunk matches any of the fact's alternative (document, evidence) pairs."""
    text = _normalise(chunk["snippet"])
    return any(
        chunk["document"] == document and _normalise(evidence) in text
        for document, evidence in fact
    )


def category(item: dict) -> str:
    """"lookup" for questions about an exact name or number; otherwise "paraphrase"."""
    return item["tags"][0] if item.get("tags") else "paraphrase"


def score_question(item: dict, ranked: list[dict], k: int) -> dict:
    facts = item["facts"]
    top_k = ranked[:k]
    found_in_k = [any(fact_found(f, c) for c in top_k) for f in facts]
    first_rank = next(
        (
            rank
            for rank, chunk in enumerate(ranked, start=1)
            if any(fact_found(f, chunk) for f in facts)
        ),
        None,
    )
    return {
        "id": item["id"],
        "question": item["question"],
        "category": category(item),
        "first_rank": first_rank,
        "hit": any(found_in_k),
        "recall": sum(found_in_k) / len(facts),
        "all_facts": all(found_in_k),
    }


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _summary(scored: list[dict], k: int) -> dict:
    def hit_at(n: int) -> float:
        return _mean(1.0 if s["first_rank"] is not None and s["first_rank"] <= n else 0.0 for s in scored)

    return {
        f"recall@{k}": _mean(s["recall"] for s in scored),
        f"hit_rate@{k}": _mean(1.0 if s["hit"] else 0.0 for s in scored),
        "mrr": _mean(1.0 / s["first_rank"] if s["first_rank"] else 0.0 for s in scored),
        "hit_rate@1": hit_at(1),
        f"hit_rate@{MAX_RANK}": hit_at(MAX_RANK),
        "all_facts_found": _mean(1.0 if s["all_facts"] else 0.0 for s in scored),
    }


def evaluate(search: Search, retrieve: Retrieve, golden: dict, k: int = 3) -> dict:
    """Score a retriever.

    search(query, n) must return the n best chunks, best first and unfiltered,
    so ranking quality is measured on its own. retrieve(query) is what the
    agent actually receives (after any cutoff), used for the no-answer checks.
    """
    scored = [score_question(item, search(item["question"], MAX_RANK), k) for item in golden["questions"]]

    def given_no_context(queries) -> float:
        return _mean(1.0 if not retrieve(query) else 0.0 for query in queries)

    metrics = _summary(scored, k)
    metrics["on_topic_given_no_context"] = given_no_context(item["question"] for item in golden["questions"])
    metrics["off_topic_given_no_context"] = given_no_context(golden["off_topic"])
    if golden.get("near_miss"):
        metrics["near_miss_given_no_context"] = given_no_context(golden["near_miss"])

    return {
        "dataset_version": golden.get("version"),
        "k": k,
        "questions": len(scored),
        "metrics": metrics,
        "by_category": {
            name: _summary([s for s in scored if s["category"] == name], k)
            for name in sorted({s["category"] for s in scored})
        },
        "failures": [s for s in scored if not s["hit"]],
    }


def format_report(report: dict, previous: dict | None = None) -> str:
    lines = [f"{report['questions']} questions, k={report['k']}", ""]
    for name, value in report["metrics"].items():
        delta = ""
        if previous and name in previous["metrics"]:
            change = value - previous["metrics"][name]
            delta = f"   ({change:+.3f} vs {previous['label']})"
        lines.append(f"  {name:<28}{value:6.3f}{delta}")
    for name, summary in report.get("by_category", {}).items():
        shown = "  ".join(f"{key} {value:.3f}" for key, value in summary.items() if key.startswith(("recall", "mrr", "hit_rate@1")))
        lines.append(f"    {name:<12} {shown}")
    if report["failures"]:
        lines += ["", f"Not found in the top {report['k']} ({len(report['failures'])}):"]
        for failure in report["failures"]:
            rank = failure["first_rank"]
            lines.append(f"  {failure['id']}  rank {rank or '-':>2}  {failure['question']}")
    return "\n".join(lines)


def last_logged(dataset_version: int | None = None) -> dict | None:
    """The most recent logged run, only counting runs on the same version of the
    dataset (results on different questions cannot be compared)."""
    if not HISTORY_PATH.exists():
        return None
    records = [json.loads(line) for line in HISTORY_PATH.read_text().splitlines() if line.strip()]
    if dataset_version is not None:
        records = [r for r in records if r.get("dataset_version") == dataset_version]
    return records[-1] if records else None


def log_result(label: str, report: dict) -> None:
    record = {
        "label": label,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_version": report["dataset_version"],
        "k": report["k"],
        "metrics": report["metrics"],
        "by_category": report["by_category"],
    }
    with HISTORY_PATH.open("a") as handle:
        handle.write(json.dumps(record) + "\n")


def main() -> None:
    from app.rag import retriever

    parser = argparse.ArgumentParser(description="Evaluate retrieval against the golden question set.")
    parser.add_argument("--k", type=int, default=3, help="how many chunks the agent receives")
    parser.add_argument("--log", metavar="LABEL", help="append the result to rag_eval/history.jsonl under this label")
    args = parser.parse_args()

    golden = load_golden()
    report = evaluate(
        retriever.search,
        lambda query: retriever.retrieve(query, args.k),
        golden,
        k=args.k,
    )
    print(format_report(report, last_logged(golden.get("version"))))
    if args.log:
        log_result(args.log, report)
        print(f"\nLogged as '{args.log}' in {HISTORY_PATH}")


if __name__ == "__main__":
    main()

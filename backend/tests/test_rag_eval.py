import re
from pathlib import Path

import pytest

from app.core.config import KNOWLEDGE_DIR
from app.rag import evaluate as ev


def chunk(document, text):
    return {"document": document, "section": "s", "snippet": text}


GOLDEN = {
    "questions": [
        {"id": "a", "question": "qa", "facts": [[["doc1.md", "alpha beta"]]]},
        {"id": "b", "question": "qb", "facts": [[["doc1.md", "one"]], [["doc2.md", "two"]]]},
        {"id": "c", "question": "qc", "facts": [[["doc1.md", "x1"], ["doc2.md", "x2"]]]},
    ],
    "off_topic": ["weather", "pizza"],
}


def run(rankings, retrieve=lambda q: [], k=3):
    return ev.evaluate(lambda query, n: rankings[query][:n], retrieve, GOLDEN, k=k)


def test_a_fact_needs_the_right_document_and_the_evidence_text():
    fact = [["doc1.md", "alpha beta"]]
    assert ev.fact_found(fact, chunk("doc1.md", "some alpha beta text"))
    assert not ev.fact_found(fact, chunk("doc2.md", "some alpha beta text"))
    assert not ev.fact_found(fact, chunk("doc1.md", "alpha gamma"))


def test_matching_ignores_whitespace_differences():
    assert ev.fact_found([["d.md", "alpha beta"]], chunk("d.md", "alpha\n   beta"))


def test_any_alternative_satisfies_a_fact():
    fact = [["doc1.md", "x1"], ["doc2.md", "x2"]]
    assert ev.fact_found(fact, chunk("doc2.md", "has x2"))
    assert ev.fact_found(fact, chunk("doc1.md", "has x1"))


def test_perfect_retrieval_scores_one():
    report = run({
        "qa": [chunk("doc1.md", "alpha beta")],
        "qb": [chunk("doc1.md", "one"), chunk("doc2.md", "two")],
        "qc": [chunk("doc2.md", "x2")],
    })
    m = report["metrics"]
    assert (m["recall@3"], m["hit_rate@3"], m["mrr"], m["hit_rate@1"], m["all_facts_found"]) == (1, 1, 1, 1, 1)
    assert report["failures"] == []


def test_mrr_uses_the_rank_of_the_first_relevant_chunk():
    miss = chunk("other.md", "nothing")
    report = run({
        "qa": [miss, chunk("doc1.md", "alpha beta")],            # rank 2 -> 0.5
        "qb": [miss, miss, chunk("doc1.md", "one")],              # rank 3 -> 1/3
        "qc": [chunk("doc1.md", "x1")],                           # rank 1 -> 1
    })
    assert report["metrics"]["mrr"] == pytest.approx((0.5 + 1 / 3 + 1) / 3)
    assert report["metrics"]["hit_rate@1"] == pytest.approx(1 / 3)


def test_recall_is_the_share_of_facts_found_in_the_top_k():
    miss = chunk("other.md", "nothing")
    report = run({
        "qa": [chunk("doc1.md", "alpha beta")],
        "qb": [chunk("doc1.md", "one"), miss, miss, chunk("doc2.md", "two")],   # second fact is at rank 4
        "qc": [miss],
    })
    m = report["metrics"]
    assert m["recall@3"] == pytest.approx((1 + 0.5 + 0) / 3)
    assert m["hit_rate@3"] == pytest.approx(2 / 3)
    assert m["all_facts_found"] == pytest.approx(1 / 3)
    assert m["hit_rate@10"] == pytest.approx(1.0 - 1 / 3)
    assert [f["id"] for f in report["failures"]] == ["c"]


def test_k_changes_how_deep_the_top_k_goes():
    miss = chunk("other.md", "nothing")
    rankings = {"qa": [miss, miss, chunk("doc1.md", "alpha beta")], "qb": [miss], "qc": [miss]}
    assert run(rankings, k=2)["metrics"]["hit_rate@2"] == 0
    assert run(rankings, k=3)["metrics"]["hit_rate@3"] == pytest.approx(1 / 3)


def test_no_context_rates():
    report = run(
        {"qa": [], "qb": [], "qc": []},
        retrieve=lambda query: [] if query in ("weather", "qa") else [chunk("d.md", "t")],
    )
    assert report["metrics"]["off_topic_given_no_context"] == pytest.approx(0.5)  # weather clean, pizza not
    assert report["metrics"]["on_topic_given_no_context"] == pytest.approx(1 / 3)  # only qa returned nothing


def test_report_shows_the_change_from_the_last_logged_run():
    report = run({"qa": [chunk("doc1.md", "alpha beta")], "qb": [], "qc": []})
    previous = {"label": "before", "metrics": {"mrr": 0.5, "recall@3": 0.5}}
    text = ev.format_report(report, previous)
    assert "vs before" in text and "recall@3" in text and "qb" in text


def test_logging_appends_and_the_latest_is_read_back(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "HISTORY_PATH", tmp_path / "history.jsonl")
    assert ev.last_logged() is None

    report = run({"qa": [], "qb": [], "qc": []})
    ev.log_result("first", report)
    ev.log_result("second", report)

    latest = ev.last_logged()
    assert latest["label"] == "second" and latest["k"] == 3 and "mrr" in latest["metrics"]
    assert len((tmp_path / "history.jsonl").read_text().splitlines()) == 2


# --- the dataset itself


def _corpus():
    return {
        path.name: re.sub(r"\s+", " ", path.read_text())
        for path in KNOWLEDGE_DIR.glob("**/*.md")
        if path.name != "README.md"
    }


def test_the_golden_set_is_large_enough_and_well_formed():
    golden = ev.load_golden()
    ids = [q["id"] for q in golden["questions"]]
    assert len(golden["questions"]) >= 50
    assert len(ids) == len(set(ids))
    assert len(golden["off_topic"]) >= 10
    for item in golden["questions"]:
        assert item["question"].strip() and item["facts"]
        for fact in item["facts"]:
            assert fact and all(len(alt) == 2 for alt in fact)


def test_every_evidence_phrase_is_really_in_its_document():
    corpus = _corpus()
    for item in ev.load_golden()["questions"]:
        for fact in item["facts"]:
            for document, evidence in fact:
                assert document in corpus, f"{item['id']}: no such document {document}"
                assert re.sub(r"\s+", " ", evidence) in corpus[document], (
                    f"{item['id']}: evidence not found in {document}: {evidence!r}"
                )


def test_the_corpus_has_unique_file_names():
    names = [p.name for p in Path(KNOWLEDGE_DIR).glob("**/*.md") if p.name != "README.md"]
    assert len(names) == len(set(names))

"""Run the real models over the real corpus and check the evaluation scores.

Slow (about a minute) and needs the search models downloaded, so it is skipped
unless asked for:  pytest -m slow
"""
import chromadb
import pytest

from app.rag.evaluate import evaluate, load_golden
from app.rag.ingest import ingest
from app.rag.retriever import Retriever
from app.rag.store import ChromaStore


@pytest.mark.slow
def test_retrieval_quality_on_the_golden_set(tmp_path):
    store = ChromaStore.create(chromadb.PersistentClient(path=str(tmp_path)))
    ingest(store)
    retriever = Retriever(store)

    report = evaluate(retriever.search, lambda q: retriever.retrieve(q, 3), load_golden(), k=3)
    metrics, by_category = report["metrics"], report["by_category"]

    assert metrics["recall@3"] >= 0.95
    assert metrics["mrr"] >= 0.85
    assert metrics["hit_rate@10"] >= 0.98
    assert by_category["lookup"]["recall@3"] >= 0.95, "exact names and numbers must be found"
    assert by_category["paraphrase"]["recall@3"] >= 0.95
    assert metrics["off_topic_given_no_context"] == 1.0
    assert metrics["on_topic_given_no_context"] == 0.0, "the cutoff must not hide real answers"

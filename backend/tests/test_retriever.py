import logging

import pytest

from app.rag import retriever as retriever_module
from app.rag.retriever import CANDIDATES_PER_SEARCH, RERANK_CANDIDATES, Retriever
from app.rag.store import KnowledgeBaseNotFound, StoredChunk

CHUNKS = [
    StoredChunk("lib::0", "library.md", "Hours", "Library opens at eight on weekdays"),
    StoredChunk("lib::1", "library.md", "Fines", "A library fine of five rupees per day applies"),
    StoredChunk("dir::0", "directory.md", "ECE", "Department office Room 305 third floor"),
    StoredChunk("host::0", "hostel.md", "Mess", "Hostel mess dinner timings"),
    StoredChunk("misc::0", "misc.md", "Other", "Parking permits for vehicles"),
]


class FakeStore:
    """Dense search that always answers with a fixed list, like a vector store would."""

    def __init__(self, chunks=CHUNKS, nearest=("lib::0", "host::0")):
        self.chunks = list(chunks)
        self.nearest = list(nearest)
        self.all_chunks_calls = 0

    def all_chunks(self):
        self.all_chunks_calls += 1
        return list(self.chunks)

    def query(self, text, n):
        by_id = {c.id: c for c in self.chunks}
        return [by_id[i] for i in self.nearest if i in by_id][:n]


def keyword_reranker(query, texts):
    """Scores a text by how many query words it contains."""
    words = set(query.lower().split())
    return [float(len(words & set(t.lower().split()))) for t in texts]


def make(store=None, rerank=keyword_reranker):
    return Retriever(store or FakeStore(), rerank=rerank)


def test_the_best_matches_come_first_with_their_scores():
    hits = make().search("library fine per day", 3)
    assert hits[0]["section"] == "Fines" and hits[0]["document"] == "library.md"
    assert [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True)
    assert set(hits[0]) == {"document", "section", "snippet", "score"}


def test_a_chunk_only_the_keyword_search_finds_still_reaches_the_reranker():
    # Semantic search offers only lib::0 and host::0, but "Room 305" is an exact keyword match.
    hits = make().search("Room 305", 3)
    assert hits[0]["document"] == "directory.md"


def test_a_chunk_only_semantic_search_finds_still_reaches_the_reranker():
    store = FakeStore(nearest=("misc::0", "lib::0"))
    hits = make(store, rerank=lambda q, texts: [1.0 if "Parking" in t else 0.0 for t in texts]).search("zzzz unrelated", 3)
    assert hits[0]["document"] == "misc.md"


def test_the_reranker_decides_the_final_order():
    def prefers(word):
        return lambda query, texts: [1.0 if word in t else 0.0 for t in texts]

    assert make(rerank=prefers("fine")).search("library", 3)[0]["section"] == "Fines"
    assert make(rerank=prefers("eight")).search("library", 3)[0]["section"] == "Hours"


def test_the_reranker_is_given_the_question_and_the_candidates_text():
    seen = {}

    def spy(query, texts):
        seen.update(query=query, texts=texts)
        return [0.0] * len(texts)

    make(rerank=spy).search("library fine", 2)

    assert seen["query"] == "library fine"
    assert all(isinstance(t, str) for t in seen["texts"]) and 2 <= len(seen["texts"]) <= RERANK_CANDIDATES


def test_n_limits_how_many_come_back():
    assert len(make().search("library", 1)) == 1
    assert len(make().search("library", 5)) <= 5


def test_retrieve_hands_over_only_what_the_reranker_calls_relevant(monkeypatch):
    monkeypatch.setattr(retriever_module, "RAG_RERANK_MIN_SCORE", 1.0)
    hits = make().retrieve("library fine per day", 5)
    assert hits and all(set(h) == {"document", "section", "snippet"} for h in hits)
    assert all("library" in h["snippet"].lower() or "fine" in h["snippet"].lower() for h in hits)


def test_retrieve_returns_nothing_when_nothing_is_relevant_enough(monkeypatch):
    monkeypatch.setattr(retriever_module, "RAG_RERANK_MIN_SCORE", 100.0)
    assert make().retrieve("library", 3) == []


def test_the_threshold_keeps_a_score_exactly_at_the_limit(monkeypatch):
    monkeypatch.setattr(retriever_module, "RAG_RERANK_MIN_SCORE", -8.5)
    assert len(make(rerank=lambda q, texts: [-8.5] * len(texts)).retrieve("library", 2)) == 2
    assert make(rerank=lambda q, texts: [-8.6] * len(texts)).retrieve("library", 2) == []


def test_k_limits_what_retrieve_returns(monkeypatch):
    monkeypatch.setattr(retriever_module, "RAG_RERANK_MIN_SCORE", -100.0)
    assert len(make().retrieve("library", 2)) == 2


def test_an_empty_knowledge_base_is_reported():
    with pytest.raises(KnowledgeBaseNotFound):
        make(FakeStore(chunks=[])).search("anything", 3)


def test_a_stale_keyword_index_cannot_break_a_search():
    # The semantic search returns a chunk the (older) keyword snapshot has never seen.
    store = FakeStore()
    retriever = make(store)
    retriever.search("library", 3)
    store.chunks.append(StoredChunk("new::0", "new.md", "S", "Brand new parking information"))
    store.nearest = ["new::0", "lib::0"]
    assert any(h["document"] == "new.md" for h in retriever.search("parking", 3))


def test_the_keyword_index_is_reused_within_its_lifetime():
    store = FakeStore()
    retriever = make(store)
    retriever.search("library", 3)
    retriever.search("hostel", 3)
    assert store.all_chunks_calls == 1


def test_after_its_lifetime_a_changed_store_is_picked_up(monkeypatch):
    monkeypatch.setattr(retriever_module, "INDEX_TTL_SECONDS", 0.0)
    store = FakeStore()
    retriever = make(store)
    assert retriever.search("swimming pool", 3)[0]["score"] == 0

    store.chunks.append(StoredChunk("pool::0", "sports.md", "Pool", "Swimming pool open February to November"))
    store.nearest = []
    assert retriever.search("swimming pool", 3)[0]["document"] == "sports.md"


def test_after_its_lifetime_an_unchanged_store_keeps_the_same_index(monkeypatch):
    monkeypatch.setattr(retriever_module, "INDEX_TTL_SECONDS", 0.0)
    retriever = make()
    retriever.search("library", 3)
    first = retriever._snapshot
    retriever.search("library", 3)
    assert retriever._snapshot is first


def test_the_two_searches_each_look_this_deep():
    seen = []

    class Spy(FakeStore):
        def query(self, text, n):
            seen.append(n)
            return super().query(text, n)

    make(Spy()).search("library", 3)
    assert seen == [CANDIDATES_PER_SEARCH]


# --- the shared retriever


def test_the_shared_retriever_is_created_once_and_can_be_reset(monkeypatch):
    opened = []
    monkeypatch.setattr(retriever_module.ChromaStore, "open", lambda client: opened.append(1) or FakeStore())
    monkeypatch.setattr(retriever_module, "get_client", lambda: object())
    retriever_module.reset_retriever()
    try:
        assert retriever_module.get_retriever() is retriever_module.get_retriever()
        assert len(opened) == 1
        retriever_module.reset_retriever()
        retriever_module.get_retriever()
        assert len(opened) == 2
    finally:
        retriever_module.reset_retriever()


def test_warming_up_never_raises_and_says_why(monkeypatch, caplog):
    def missing():
        raise KnowledgeBaseNotFound("Knowledge base not found.")

    monkeypatch.setattr(retriever_module, "get_retriever", missing)
    with caplog.at_level(logging.WARNING):
        retriever_module.warm_up()
    assert "Knowledge base not found" in caplog.text

    def broken():
        raise RuntimeError("model failed to load")

    monkeypatch.setattr(retriever_module, "get_retriever", broken)
    retriever_module.warm_up()


def test_the_module_level_functions_use_the_shared_retriever(monkeypatch):
    shared = make()
    monkeypatch.setattr(retriever_module, "get_retriever", lambda: shared)
    assert retriever_module.search("library fine", 2) == shared.search("library fine", 2)
    assert retriever_module.retrieve("library fine", 2) == shared.retrieve("library fine", 2)

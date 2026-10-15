from app.rag import retriever


class FakeCollection:
    def __init__(self, distances):
        self._distances = distances

    def query(self, query_texts, n_results):
        n = len(self._distances)
        return {
            "documents": [[f"text {i}" for i in range(n)]],
            "metadatas": [[{"document": f"doc{i}", "section": f"sec{i}"} for i in range(n)]],
            "distances": [self._distances],
        }


def test_chunks_beyond_max_distance_are_dropped(monkeypatch):
    distances = [0.5, retriever.MAX_DISTANCE, retriever.MAX_DISTANCE + 0.01]
    monkeypatch.setattr(retriever, "_get_collection", lambda: FakeCollection(distances))

    chunks = retriever.retrieve("anything")

    assert [c["document"] for c in chunks] == ["doc0", "doc1"]
    assert chunks[0] == {"document": "doc0", "section": "sec0", "snippet": "text 0"}


def test_all_chunks_too_far_returns_empty_list(monkeypatch):
    monkeypatch.setattr(retriever, "_get_collection", lambda: FakeCollection([2.0, 3.0]))
    assert retriever.retrieve("anything") == []

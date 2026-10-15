import subprocess
import sys

import chromadb
import pytest

from app.rag import retriever as retriever_module
from app.rag import store as store_module
from app.rag.retriever import Retriever
from app.rag.store import ChromaStore, KnowledgeBaseNotFound, QdrantStore, create_store, describe_store, open_store


def test_the_configured_database_is_the_one_used(chroma_client):
    assert isinstance(create_store(), ChromaStore) and isinstance(open_store(), ChromaStore)


def test_qdrant_is_used_when_selected(qdrant_client):
    assert isinstance(create_store(), QdrantStore) and isinstance(open_store(), QdrantStore)


def test_a_chroma_server_is_used_when_a_host_is_set(monkeypatch):
    made = {}
    monkeypatch.setattr(store_module, "CHROMA_HOST", "chroma.internal")
    monkeypatch.setattr(store_module, "CHROMA_PORT", 8123)
    monkeypatch.setattr(chromadb, "HttpClient", lambda host, port: made.update(host=host, port=port) or "client")

    assert store_module._chroma_client() == "client"
    assert made == {"host": "chroma.internal", "port": 8123}


def test_local_chroma_files_are_used_without_a_host(monkeypatch, tmp_path):
    monkeypatch.setattr(store_module, "CHROMA_HOST", "")
    monkeypatch.setattr(store_module, "CHROMA_DIR", tmp_path)
    monkeypatch.setattr(chromadb, "PersistentClient", lambda path: ("local", path))
    assert store_module._chroma_client() == ("local", str(tmp_path))


@pytest.mark.parametrize(
    "setup, expected",
    [
        ({"VECTOR_STORE": "chroma", "CHROMA_HOST": ""}, "Chroma files in"),
        ({"VECTOR_STORE": "chroma", "CHROMA_HOST": "box", "CHROMA_PORT": 9}, "Chroma server at box:9"),
        ({"VECTOR_STORE": "qdrant", "QDRANT_URL": "http://q:6333"}, "Qdrant at http://q:6333"),
    ],
)
def test_the_store_describes_where_it_lives(monkeypatch, setup, expected):
    for name, value in setup.items():
        monkeypatch.setattr(store_module, name, value)
    assert expected in describe_store()


def test_an_unknown_database_name_stops_startup_with_a_clear_message():
    result = subprocess.run(
        [sys.executable, "-c", "import app.core.config"],
        env={"VECTOR_STORE": "mongo", "PATH": "/usr/bin", "JWT_SECRET": "x" * 40},
        capture_output=True, text=True, cwd=".",
    )
    assert result.returncode != 0 and "VECTOR_STORE must be 'chroma' or 'qdrant'" in result.stderr


class BrokenStore:
    def all_chunks(self):
        raise ConnectionError("connection refused")

    def query(self, text, n):
        raise ConnectionError("connection refused")


def test_an_unreachable_store_counts_as_an_unusable_knowledge_base(caplog):
    with caplog.at_level("ERROR"):
        with pytest.raises(KnowledgeBaseNotFound, match="could not be reached"):
            Retriever(BrokenStore(), rerank=lambda q, t: []).search("anything", 3)
    assert "connection refused" in caplog.text


def test_a_store_that_fails_during_the_semantic_search_is_handled_too():
    class OnlyQueryFails(BrokenStore):
        def all_chunks(self):
            return [store_module.StoredChunk("a::0", "a.md", "S", "some text")]

    with pytest.raises(KnowledgeBaseNotFound):
        Retriever(OnlyQueryFails(), rerank=lambda q, t: []).search("text", 3)


def test_bugs_in_our_own_code_are_not_disguised_as_an_unreachable_store():
    class Buggy(BrokenStore):
        def all_chunks(self):
            return [store_module.StoredChunk("a::0", "a.md", "S", "text")]

        def query(self, text, n):
            return []

    def broken_rerank(query, texts):
        raise ZeroDivisionError("a real bug")

    with pytest.raises(ZeroDivisionError):
        Retriever(Buggy(), rerank=broken_rerank).search("text", 3)

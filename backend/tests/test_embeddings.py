from types import SimpleNamespace

import openai
import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.core.errors import AppError
from app.main import app
from app.rag import embeddings as emb
from app.rag import ingest as ingest_module
from app.rag import store as store_module
from app.rag.embeddings import (
    BaseEmbeddingFunction,
    MiniLMEmbedding,
    OllamaEmbedding,
    OpenAIEmbedding,
    get_embedding_function,
)
from app.rag.store import EmbeddingSettingsChanged, KnowledgeBaseNotFound
from fakes import FakeEmbedding
from helpers import ADMIN, sign_in_as


class RawEmbeddings:
    """A fake SDK client: embeddings.create(model, input) -> data with index and embedding."""

    def __init__(self, size=3, shuffle=False):
        self.calls = []
        self._size, self._shuffle = size, shuffle
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, model, input):
        self.calls.append((model, list(input)))
        items = [SimpleNamespace(index=i, embedding=[float(len(text))] * self._size) for i, text in enumerate(input)]
        return SimpleNamespace(data=list(reversed(items)) if self._shuffle else items)


# --- the interface


def test_a_provider_must_implement_embed():
    class Incomplete(BaseEmbeddingFunction):
        identity = "x"

    with pytest.raises(TypeError):
        Incomplete()


def test_calling_an_embedding_function_embeds_like_chroma_expects():
    fake = FakeEmbedding()
    assert [list(v) for v in fake(["a b", "c"])] == fake.embed(["a b", "c"])


def test_the_dimension_is_probed_once():
    raw = RawEmbeddings(size=7)
    function = OllamaEmbedding(raw=raw, model="m")
    assert (function.dimensions, function.dimensions) == (7, 7) and len(raw.calls) == 1


# --- the three providers


def test_the_local_model_is_the_one_the_knowledge_base_was_built_with():
    local = MiniLMEmbedding()
    assert local.identity == "all-MiniLM-L6-v2" and local.name() == "default" and local.dimensions == 384
    vectors = local.embed(["library hours", "hostel curfew"])
    assert len(vectors) == 2 and len(vectors[0]) == 384 and all(isinstance(x, float) for x in vectors[0])


def test_ollama_embeds_through_its_openai_compatible_endpoint(monkeypatch):
    raw = RawEmbeddings()
    function = OllamaEmbedding(raw=raw)
    assert function.identity == "ollama:nomic-embed-text"
    assert function.embed(["ab", "cde"]) == [[2.0] * 3, [3.0] * 3] and raw.calls == [("nomic-embed-text", ["ab", "cde"])]


def test_openai_defaults_to_the_small_embedding_model_and_a_model_can_be_named(monkeypatch):
    assert OpenAIEmbedding(raw=RawEmbeddings()).identity == "openai:text-embedding-3-small"
    monkeypatch.setattr(config, "EMBEDDING_MODEL", "text-embedding-3-large")
    assert OpenAIEmbedding(raw=RawEmbeddings()).identity == "openai:text-embedding-3-large"


def test_results_are_put_back_in_the_order_of_the_inputs():
    function = OllamaEmbedding(raw=RawEmbeddings(shuffle=True), model="m")
    assert function.embed(["a", "bb", "ccc"]) == [[1.0] * 3, [2.0] * 3, [3.0] * 3]


def test_many_texts_are_sent_in_batches():
    raw = RawEmbeddings()
    function = OllamaEmbedding(raw=raw, model="m")
    assert len(function.embed([f"t{i}" for i in range(150)])) == 150
    assert [len(c[1]) for c in raw.calls] == [64, 64, 22]


def test_openai_needs_a_key_unless_a_server_of_your_own_is_named(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIEmbedding()
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "http://localhost:9/v1")
    assert OpenAIEmbedding().identity == "openai:text-embedding-3-small"


def test_the_ollama_function_points_at_the_configured_server(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://box:11434/v1")
    function = OllamaEmbedding()
    assert isinstance(function._raw, openai.OpenAI) and str(function._raw.base_url).startswith("http://box:11434/v1")


# --- choosing one


@pytest.fixture
def provider(monkeypatch):
    def pick(name):
        monkeypatch.setattr(config, "EMBEDDING_PROVIDER", name)
        get_embedding_function.cache_clear()

    yield pick
    get_embedding_function.cache_clear()


def test_local_is_the_default(provider):
    provider("local")
    assert isinstance(get_embedding_function(), MiniLMEmbedding)


def test_the_provider_can_be_switched(provider, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "http://localhost:11434/v1")
    provider("ollama")
    assert isinstance(get_embedding_function(), OllamaEmbedding)


def test_an_unknown_provider_is_a_clear_error(provider):
    provider("quantum")
    with pytest.raises(ValueError, match="EMBEDDING_PROVIDER must be one of local, ollama, openai"):
        get_embedding_function()


# --- changing the model means rebuilding


class OtherEmbedding(FakeEmbedding):
    identity = "other-model"

    @staticmethod
    def name():
        return "other-embedding"


def test_ingest_refuses_to_mix_models_and_says_how_to_fix_it(chroma_client, monkeypatch, tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n## S\n\nSome words about the library.\n")
    store = store_module.create_store()
    ingest_module.ingest(store, tmp_path)

    monkeypatch.setattr(ingest_module, "get_embedding_function", lambda: OtherEmbedding())
    with pytest.raises(EmbeddingSettingsChanged, match="python -m app.rag.ingest --full"):
        ingest_module.ingest(store, tmp_path)


def test_the_store_itself_refuses_a_collection_built_with_another_model(chroma_client, monkeypatch, tmp_path):
    store = store_module.create_store()
    store.upsert([], "h", "chunker1:256:32:fake-embedding", "2026-01-01T00:00:00+00:00")
    monkeypatch.setattr(store_module, "get_embedding_function", lambda: OtherEmbedding())
    with pytest.raises(EmbeddingSettingsChanged):
        store_module.open_store()


def test_a_rebuild_with_the_new_model_works(chroma_client, monkeypatch, tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n## S\n\nSome words about the library.\n")
    ingest_module.ingest(store_module.create_store(), tmp_path)
    monkeypatch.setattr(store_module, "get_embedding_function", lambda: OtherEmbedding())
    monkeypatch.setattr(ingest_module, "get_embedding_function", lambda: OtherEmbedding())
    fresh = store_module.create_store(fresh=True)
    report = ingest_module.ingest(fresh, tmp_path)
    assert report.added == ["a.md"] and fresh.documents()[0].signature.endswith("other-model")


def test_an_unusable_knowledge_base_counts_as_unavailable_not_as_a_crash():
    assert issubclass(EmbeddingSettingsChanged, KnowledgeBaseNotFound)


def test_the_admin_endpoint_reports_it_as_a_conflict(db, monkeypatch):
    from app.services import knowledge_service

    def changed(fresh=False):
        raise EmbeddingSettingsChanged("built with another model. Rebuild it with: python -m app.rag.ingest --full")

    monkeypatch.setattr(knowledge_service, "create_store", changed)
    admin = sign_in_as(ADMIN)
    response = admin.post("/api/admin/knowledge/ingest")
    assert (response.status_code, response.json()["error_code"]) == (409, "embedding_settings_changed")
    assert "full rebuild" in response.json()["message"]


def test_the_command_line_exits_with_the_message(chroma_client, monkeypatch, tmp_path):
    def changed(fresh=False):
        raise EmbeddingSettingsChanged("rebuild me")

    monkeypatch.setattr(ingest_module, "create_store", changed)
    monkeypatch.setattr("sys.argv", ["ingest"])
    with pytest.raises(SystemExit, match="rebuild me"):
        ingest_module.main()

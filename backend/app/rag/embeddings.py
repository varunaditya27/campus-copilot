from abc import ABC, abstractmethod
from functools import lru_cache

import openai
from chromadb import EmbeddingFunction
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app.core import config

BATCH_SIZE = 64


class BaseEmbeddingFunction(EmbeddingFunction, ABC):
    """Turns text into vectors. Chroma calls it directly, and the Qdrant store calls embed()."""

    # Stored with every ingested document, so changing the model is noticed and the knowledge base rebuilt.
    identity: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per text."""

    def __call__(self, input):  # the name Chroma's interface requires
        return self.embed(list(input))

    @property
    def dimensions(self) -> int:
        """The length of this model's vectors, found by embedding a probe text once."""
        if not hasattr(self, "_dimensions"):
            self._dimensions = len(self.embed(["dimension probe"])[0])
        return self._dimensions

    # Chroma stores an embedding function's name and settings with a collection and refuses a
    # different one later, which is what stops two models being mixed in one collection.
    def get_config(self) -> dict:
        return {"identity": self.identity}

    @staticmethod
    def build_from_config(config: dict):
        raise NotImplementedError("Rebuild it from the application's settings, not from a stored configuration.")


class MiniLMEmbedding(BaseEmbeddingFunction):
    """all-MiniLM-L6-v2 running locally on the ONNX runtime: no API key, no PyTorch.

    It is the same model the roadmap names under sentence-transformers; Chroma's bundled
    ONNX version is used instead because it needs no PyTorch install. Its Chroma name stays
    "default" so a knowledge base built before this layer existed still opens."""

    identity = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        self._inner = DefaultEmbeddingFunction()

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vector] for vector in self._inner(texts)]

    @staticmethod
    def name() -> str:
        return "default"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict):
        return MiniLMEmbedding()


class OpenAICompatibleEmbedding(BaseEmbeddingFunction):
    """Embeddings from a service with OpenAI's /v1/embeddings endpoint: OpenAI itself, or Ollama."""

    def __init__(self, provider: str, model: str, raw) -> None:
        self.identity = f"{provider}:{model}"
        self._provider = provider
        self._model = model
        self._raw = raw

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            response = self._raw.embeddings.create(model=self._model, input=batch)
            vectors += [[float(x) for x in item.embedding] for item in sorted(response.data, key=lambda i: i.index)]
        return vectors

    def name(self) -> str:  # type: ignore[override]
        return f"campus-{self._provider}"

    def get_config(self) -> dict:
        return {"model": self._model}

    @staticmethod
    def build_from_config(config: dict):
        raise NotImplementedError("Rebuild it from the application's settings, not from a stored configuration.")


class OpenAIEmbedding(OpenAICompatibleEmbedding):
    def __init__(self, raw=None, model: str | None = None) -> None:
        model = model or config.EMBEDDING_MODEL or "text-embedding-3-small"
        if raw is None:
            key = config.OPENAI_API_KEY or ("unused" if config.OPENAI_BASE_URL else "")
            if not key:
                raise ValueError("OPENAI_API_KEY is not set.")
            raw = openai.OpenAI(api_key=key, base_url=config.OPENAI_BASE_URL or None)
        super().__init__("openai", model, raw)


class OllamaEmbedding(OpenAICompatibleEmbedding):
    """Fully local: a model such as nomic-embed-text, pulled into Ollama."""

    def __init__(self, raw=None, model: str | None = None) -> None:
        model = model or config.EMBEDDING_MODEL or "nomic-embed-text"
        raw = raw or openai.OpenAI(api_key="ollama", base_url=config.OLLAMA_BASE_URL)
        super().__init__("ollama", model, raw)


EMBEDDING_PROVIDERS = {"local": MiniLMEmbedding, "ollama": OllamaEmbedding, "openai": OpenAIEmbedding}


@lru_cache
def get_embedding_function() -> BaseEmbeddingFunction:
    """The embedding model for the configured EMBEDDING_PROVIDER."""
    try:
        return EMBEDDING_PROVIDERS[config.EMBEDDING_PROVIDER]()
    except KeyError:
        raise ValueError(
            f"EMBEDDING_PROVIDER must be one of {', '.join(EMBEDDING_PROVIDERS)}, not '{config.EMBEDDING_PROVIDER}'."
        ) from None

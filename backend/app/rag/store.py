import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import chromadb
from qdrant_client import QdrantClient, models

from app.core.config import (
    CHROMA_DIR,
    CHROMA_HOST,
    CHROMA_PORT,
    KNOWLEDGE_COLLECTION,
    QDRANT_API_KEY,
    QDRANT_URL,
    VECTOR_STORE,
)
from app.rag.chunking import Chunk
from app.rag.embeddings import get_embedding_function


class KnowledgeBaseNotFound(RuntimeError):
    """The knowledge base cannot be used: it was never built, or cannot be reached."""


class EmbeddingSettingsChanged(KnowledgeBaseNotFound):
    """The knowledge base was built with a different embedding model than the one configured now.

    Vectors from different models cannot be compared (they may not even be the same length), so
    the knowledge base has to be rebuilt from the documents. Until then it counts as unavailable
    and the assistant says so instead of searching with mismatched vectors."""


def _changed() -> EmbeddingSettingsChanged:
    return EmbeddingSettingsChanged(
        f"The knowledge base was built with a different embedding model than '{get_embedding_function().identity}'. "
        "Rebuild it with: python -m app.rag.ingest --full"
    )


@dataclass(frozen=True)
class StoredChunk:
    id: str
    document: str
    section: str
    text: str
    distance: float | None = None  # set on semantic-search results only; smaller is closer


@dataclass(frozen=True)
class DocumentInfo:
    """What is recorded about an ingested document, to tell whether it is up to date."""

    document: str
    file_hash: str
    signature: str  # the chunking and embedding settings it was ingested with
    chunk_count: int
    ingested_at: str


class VectorStore(Protocol):
    """Everything retrieval and ingestion need from a vector database.

    Chunks are embedded here, with the embedding model in embeddings.py, so
    different databases hold identical vectors and give comparable results.
    """

    def count(self) -> int: ...

    def query(self, text: str, n: int) -> list[StoredChunk]:
        """The n chunks whose meaning is closest to the text, best first."""

    def all_chunks(self) -> list[StoredChunk]: ...

    def documents(self) -> list[DocumentInfo]: ...

    def upsert(self, chunks: list[Chunk], file_hash: str, signature: str, ingested_at: str) -> None: ...

    def delete_document(self, document: str) -> int:
        """Remove every chunk of a document. Returns how many there were."""

    def reset(self) -> "VectorStore":
        """Drop everything and return an empty store."""


def _group_documents(metadatas: list[dict]) -> list[DocumentInfo]:
    grouped: dict[str, list[dict]] = {}
    for meta in metadatas:
        grouped.setdefault(meta["document"], []).append(meta)
    return [
        DocumentInfo(
            document=name,
            # An index built by an older version has none of these, so it never
            # matches a real hash and gets refreshed on the next ingest.
            file_hash=metas[0].get("file_hash", ""),
            signature=metas[0].get("signature", ""),
            chunk_count=len(metas),
            ingested_at=metas[0].get("ingested_at", ""),
        )
        for name, metas in sorted(grouped.items())
    ]


def _metadata(chunk: Chunk, file_hash: str, signature: str, ingested_at: str) -> dict:
    return {
        "document": chunk.document,
        "section": chunk.section,
        "chunk_index": chunk.index,
        "file_hash": file_hash,
        "signature": signature,
        "ingested_at": ingested_at,
    }


class ChromaStore:
    """Chroma, either as local files or through a Chroma server."""

    def __init__(self, client, collection) -> None:
        self._client = client
        self._collection = collection

    @classmethod
    def open(cls, client) -> "ChromaStore":
        """The existing collection, or KnowledgeBaseNotFound if it was never built."""
        try:
            collection = client.get_collection(
                name=KNOWLEDGE_COLLECTION, embedding_function=get_embedding_function()
            )
        except ValueError as exc:
            if "embedding function" in str(exc).lower():
                raise _changed() from exc
            raise
        except Exception as exc:
            raise KnowledgeBaseNotFound(
                "Knowledge base not found. Run `python -m app.rag.ingest` first."
            ) from exc
        return cls(client, collection)

    @classmethod
    def create(cls, client) -> "ChromaStore":
        try:
            collection = client.get_or_create_collection(
                name=KNOWLEDGE_COLLECTION, embedding_function=get_embedding_function()
            )
        except ValueError as exc:
            if "embedding function" in str(exc).lower():
                raise _changed() from exc
            raise
        return cls(client, collection)

    def count(self) -> int:
        return self._collection.count()

    def query(self, text: str, n: int) -> list[StoredChunk]:
        n = min(n, self.count())
        if n == 0:
            return []
        results = self._collection.query(query_texts=[text], n_results=n)
        return [
            StoredChunk(chunk_id, meta["document"], meta["section"], document, distance)
            for chunk_id, document, meta, distance in zip(
                results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
            )
        ]

    def all_chunks(self) -> list[StoredChunk]:
        data = self._collection.get(include=["documents", "metadatas"])
        chunks = [
            StoredChunk(chunk_id, meta["document"], meta["section"], document)
            for chunk_id, document, meta in zip(data["ids"], data["documents"], data["metadatas"])
        ]
        return sorted(chunks, key=lambda c: c.id)

    def documents(self) -> list[DocumentInfo]:
        return _group_documents(self._collection.get(include=["metadatas"])["metadatas"])

    def upsert(self, chunks: list[Chunk], file_hash: str, signature: str, ingested_at: str) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[f"{c.document}::{c.index}" for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[_metadata(c, file_hash, signature, ingested_at) for c in chunks],
        )

    def delete_document(self, document: str) -> int:
        ids = self._collection.get(where={"document": document})["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def reset(self) -> "ChromaStore":
        try:
            self._client.delete_collection(name=KNOWLEDGE_COLLECTION)
        except Exception:
            pass  # it did not exist yet
        return ChromaStore.create(self._client)


class QdrantStore:
    """Qdrant. Vectors are computed here and sent with each chunk."""

    UPSERT_BATCH = 128

    def __init__(self, client: QdrantClient) -> None:
        self._client = client
        self._embedding = get_embedding_function()

    @classmethod
    def open(cls, client: QdrantClient) -> "QdrantStore":
        if not client.collection_exists(KNOWLEDGE_COLLECTION):
            raise KnowledgeBaseNotFound("Knowledge base not found. Run `python -m app.rag.ingest` first.")
        store = cls(client)
        built_with = client.get_collection(KNOWLEDGE_COLLECTION).config.params.vectors.size
        if built_with != store._embedding.dimensions:
            raise _changed()
        return store

    @classmethod
    def create(cls, client: QdrantClient) -> "QdrantStore":
        store = cls(client)
        if not client.collection_exists(KNOWLEDGE_COLLECTION):
            # The vector length belongs to the embedding model, so ask it.
            size = store._embedding.dimensions
            client.create_collection(
                KNOWLEDGE_COLLECTION,
                vectors_config=models.VectorParams(size=size, distance=models.Distance.COSINE),
            )
            # Deleting a document filters on this field; the index keeps that fast.
            client.create_payload_index(KNOWLEDGE_COLLECTION, "document", models.PayloadSchemaType.KEYWORD)
        return store

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return self._embedding.embed(texts)

    @staticmethod
    def _point_id(chunk_id: str) -> str:
        # Qdrant ids must be integers or UUIDs, so derive a stable UUID from ours.
        return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

    @staticmethod
    def _of_document(document: str) -> models.Filter:
        return models.Filter(must=[models.FieldCondition(key="document", match=models.MatchValue(value=document))])

    def count(self) -> int:
        return self._client.count(KNOWLEDGE_COLLECTION, exact=True).count

    def query(self, text: str, n: int) -> list[StoredChunk]:
        n = min(n, self.count())
        if n == 0:
            return []
        response = self._client.query_points(
            KNOWLEDGE_COLLECTION, query=self._embed([text])[0], limit=n, with_payload=True
        )
        return [
            StoredChunk(
                p.payload["id"], p.payload["document"], p.payload["section"], p.payload["text"],
                distance=1.0 - p.score,  # cosine similarity, turned into a distance
            )
            for p in response.points
        ]

    def _payloads(self) -> list[dict]:
        payloads: list[dict] = []
        offset = None
        while True:
            points, offset = self._client.scroll(KNOWLEDGE_COLLECTION, limit=256, offset=offset, with_payload=True)
            payloads += [p.payload for p in points]
            if offset is None:
                return payloads

    def all_chunks(self) -> list[StoredChunk]:
        chunks = [StoredChunk(p["id"], p["document"], p["section"], p["text"]) for p in self._payloads()]
        return sorted(chunks, key=lambda c: c.id)

    def documents(self) -> list[DocumentInfo]:
        return _group_documents(self._payloads())

    def upsert(self, chunks: list[Chunk], file_hash: str, signature: str, ingested_at: str) -> None:
        for start in range(0, len(chunks), self.UPSERT_BATCH):
            batch = chunks[start : start + self.UPSERT_BATCH]
            vectors = self._embed([c.text for c in batch])
            self._client.upsert(
                KNOWLEDGE_COLLECTION,
                points=[
                    models.PointStruct(
                        id=self._point_id(f"{c.document}::{c.index}"),
                        vector=vector,
                        payload={
                            "id": f"{c.document}::{c.index}",
                            "text": c.text,
                            **_metadata(c, file_hash, signature, ingested_at),
                        },
                    )
                    for c, vector in zip(batch, vectors)
                ],
            )

    def delete_document(self, document: str) -> int:
        selector = self._of_document(document)
        removed = self._client.count(KNOWLEDGE_COLLECTION, count_filter=selector, exact=True).count
        if removed:
            self._client.delete(KNOWLEDGE_COLLECTION, points_selector=models.FilterSelector(filter=selector))
        return removed

    def reset(self) -> "QdrantStore":
        if self._client.collection_exists(KNOWLEDGE_COLLECTION):
            self._client.delete_collection(KNOWLEDGE_COLLECTION)
        return QdrantStore.create(self._client)


def _chroma_client():
    if CHROMA_HOST:
        return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


@lru_cache
def _qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)


def open_store() -> VectorStore:
    """The configured vector store, which must already have been built."""
    if VECTOR_STORE == "qdrant":
        return QdrantStore.open(_qdrant_client())
    return ChromaStore.open(_chroma_client())


def create_store(fresh: bool = False) -> VectorStore:
    """The configured vector store, created if it does not exist yet. With fresh=True anything
    already there is dropped first, even if it was built with a different embedding model."""
    if VECTOR_STORE == "qdrant":
        client = _qdrant_client()
        if fresh and client.collection_exists(KNOWLEDGE_COLLECTION):
            client.delete_collection(KNOWLEDGE_COLLECTION)
        return QdrantStore.create(client)
    client = _chroma_client()
    if fresh:
        try:
            client.delete_collection(name=KNOWLEDGE_COLLECTION)
        except Exception:
            pass  # it did not exist yet
    return ChromaStore.create(client)


def describe_store() -> str:
    if VECTOR_STORE == "qdrant":
        return f"Qdrant at {QDRANT_URL}"
    return f"Chroma server at {CHROMA_HOST}:{CHROMA_PORT}" if CHROMA_HOST else f"Chroma files in {CHROMA_DIR}"

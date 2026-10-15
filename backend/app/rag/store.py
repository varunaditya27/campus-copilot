from dataclasses import dataclass

import chromadb

from app.core.config import CHROMA_COLLECTION, CHROMA_DIR
from app.rag.chunking import Chunk
from app.rag.embeddings import get_embedding_function


class KnowledgeBaseNotFound(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredChunk:
    id: str
    document: str
    section: str
    text: str
    distance: float | None = None  # set on semantic-search results only


@dataclass(frozen=True)
class DocumentInfo:
    """What is recorded about an ingested document, to tell whether it is up to date."""

    document: str
    file_hash: str
    signature: str  # the chunking and embedding settings it was ingested with
    chunk_count: int
    ingested_at: str


class ChromaStore:
    """The vector store, holding every chunk with its embedding.

    Retrieval and ingestion only use these methods, so another vector database
    can be swapped in by writing another class with the same methods.
    """

    def __init__(self, collection) -> None:
        self._collection = collection

    @classmethod
    def open(cls, client) -> "ChromaStore":
        """The existing collection, or KnowledgeBaseNotFound if it was never built."""
        try:
            collection = client.get_collection(
                name=CHROMA_COLLECTION, embedding_function=get_embedding_function()
            )
        except Exception as exc:
            raise KnowledgeBaseNotFound(
                "Knowledge base not found. Run `python -m app.rag.ingest` first."
            ) from exc
        return cls(collection)

    @classmethod
    def create(cls, client) -> "ChromaStore":
        collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION, embedding_function=get_embedding_function()
        )
        return cls(collection)

    def count(self) -> int:
        return self._collection.count()

    def query(self, text: str, n: int) -> list[StoredChunk]:
        """The n chunks whose meaning is closest to the text, best first."""
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
        data = self._collection.get(include=["metadatas"])
        grouped: dict[str, list[dict]] = {}
        for meta in data["metadatas"]:
            grouped.setdefault(meta["document"], []).append(meta)
        return [
            DocumentInfo(
                document=name,
                # An index built by an older version has none of these, so it
                # never matches a real hash and gets refreshed on the next ingest.
                file_hash=metas[0].get("file_hash", ""),
                signature=metas[0].get("signature", ""),
                chunk_count=len(metas),
                ingested_at=metas[0].get("ingested_at", ""),
            )
            for name, metas in sorted(grouped.items())
        ]

    def upsert(self, chunks: list[Chunk], file_hash: str, signature: str, ingested_at: str) -> None:
        if not chunks:
            return
        self._collection.upsert(
            ids=[f"{c.document}::{c.index}" for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "document": c.document,
                    "section": c.section,
                    "chunk_index": c.index,
                    "file_hash": file_hash,
                    "signature": signature,
                    "ingested_at": ingested_at,
                }
                for c in chunks
            ],
        )

    def delete_document(self, document: str) -> int:
        """Remove every chunk of a document. Returns how many there were."""
        ids = self._collection.get(where={"document": document})["ids"]
        if ids:
            self._collection.delete(ids=ids)
        return len(ids)

    def reset(self, client) -> "ChromaStore":
        """Drop the whole collection and start an empty one."""
        try:
            client.delete_collection(name=CHROMA_COLLECTION)
        except Exception:
            pass  # it did not exist yet
        return ChromaStore.create(client)


def get_client():
    return chromadb.PersistentClient(path=str(CHROMA_DIR))

from functools import lru_cache

import chromadb

from app.core.config import CHROMA_COLLECTION, CHROMA_DIR, MAX_DISTANCE
from app.rag.embeddings import get_embedding_function


class KnowledgeBaseNotFound(RuntimeError):
    pass


@lru_cache
def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        return client.get_collection(
            name=CHROMA_COLLECTION, embedding_function=get_embedding_function()
        )
    except Exception as exc:
        raise KnowledgeBaseNotFound(
            "Knowledge base not found. Run `python -m app.rag.ingest` first."
        ) from exc


def retrieve(query: str, k: int = 3) -> list[dict]:
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=k)

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    return [
        {"document": meta["document"], "section": meta["section"], "snippet": doc}
        for doc, meta, distance in zip(documents, metadatas, distances)
        if distance <= MAX_DISTANCE
    ]

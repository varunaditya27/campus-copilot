from functools import lru_cache

import chromadb

from app.core.config import CHROMA_COLLECTION, CHROMA_DIR
from app.rag.embeddings import get_embedding_function


@lru_cache
def _get_collection():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        return client.get_collection(
            name=CHROMA_COLLECTION, embedding_function=get_embedding_function()
        )
    except Exception as exc:
        raise RuntimeError(
            "Knowledge base not found. Run `python -m app.rag.ingest` first."
        ) from exc


# Chunks farther than this (L2 distance, all-MiniLM-L6-v2) are treated as
# "not actually about this" rather than force-fed to the model as context.
# Calibrated empirically: on-topic queries against this corpus land at
# ~0.7-1.3, off-topic queries land at ~1.8+.
MAX_DISTANCE = 1.5


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

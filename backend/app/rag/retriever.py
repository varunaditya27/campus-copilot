import logging
import threading
import time
from collections.abc import Callable

from app.core.config import RAG_RERANK_MIN_SCORE, RAG_RRF_K, RAG_TOP_K
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.lexical import KeywordIndex
from app.rag.rerank import rerank_scores
from app.rag.store import ChromaStore, KnowledgeBaseNotFound, StoredChunk, get_client

__all__ = ["KnowledgeBaseNotFound", "Retriever", "get_retriever", "reset_retriever", "retrieve", "search", "warm_up"]

logger = logging.getLogger(__name__)

# How many candidates each of the two searches (by meaning, by keywords)
# contributes, and how many of the merged list the reranker reads. The
# evaluation set showed reranking 10 is as good as 20 or 30, and cheaper.
CANDIDATES_PER_SEARCH = 30
RERANK_CANDIDATES = 10

# How long the keyword index is trusted before checking whether the store changed.
INDEX_TTL_SECONDS = 5.0


class _KeywordSnapshot:
    def __init__(self, chunks: list[StoredChunk]) -> None:
        self.chunks = chunks
        self.index = KeywordIndex([c.text for c in chunks])
        self.signature = tuple((c.id, hash(c.text)) for c in chunks)
        self.built_at = time.monotonic()


class Retriever:
    """Finds the passages that answer a question.

    A question is searched two ways, by meaning (embeddings) and by words
    (BM25), because each finds things the other misses: meaning copes with
    rephrased questions, words with exact names and numbers. The two rankings
    are merged (Reciprocal Rank Fusion), and a cross-encoder reads the best
    candidates alongside the question to put them in their final order.
    """

    def __init__(
        self,
        store: ChromaStore,
        rerank: Callable[[str, list[str]], list[float]] = rerank_scores,
    ) -> None:
        self._store = store
        self._rerank = rerank
        self._snapshot: _KeywordSnapshot | None = None
        self._lock = threading.Lock()

    def _keywords(self) -> _KeywordSnapshot:
        """The keyword index, rebuilt if the store has changed (for example after an ingest)."""
        snapshot = self._snapshot
        if snapshot is not None and time.monotonic() - snapshot.built_at < INDEX_TTL_SECONDS:
            return snapshot
        with self._lock:
            chunks = self._store.all_chunks()
            if not chunks:
                raise KnowledgeBaseNotFound("The knowledge base is empty. Run `python -m app.rag.ingest`.")
            current = self._snapshot
            signature = tuple((c.id, hash(c.text)) for c in chunks)
            if current is None or current.signature != signature:
                current = _KeywordSnapshot(chunks)
            else:
                current.built_at = time.monotonic()
            self._snapshot = current
            return current

    def invalidate(self) -> None:
        """Rebuild the keyword index on the next search, for use after the store changed."""
        self._snapshot = None

    def warm_up(self) -> None:
        """Load the models and build the keyword index now, by running one search."""
        self.search("campus", 1)

    def search(self, query: str, n: int) -> list[dict]:
        """The n best passages, best first, each with its reranker score. No cutoff."""
        keywords = self._keywords()
        by_meaning = self._store.query(query, CANDIDATES_PER_SEARCH)
        by_words = [keywords.chunks[position] for position, _ in keywords.index.search(query, CANDIDATES_PER_SEARCH)]

        known = {c.id: c for c in keywords.chunks}
        known.update({c.id: c for c in by_meaning})
        fused = reciprocal_rank_fusion([[c.id for c in by_meaning], [c.id for c in by_words]], k=RAG_RRF_K)
        candidates = [known[chunk_id] for chunk_id, _ in fused[: max(n, RERANK_CANDIDATES)]]

        scores = self._rerank(query, [c.text for c in candidates])
        ranked = sorted(zip(candidates, scores), key=lambda pair: pair[1], reverse=True)[:n]
        return [
            {"document": c.document, "section": c.section, "snippet": c.text, "score": score}
            for c, score in ranked
        ]

    def retrieve(self, query: str, k: int = RAG_TOP_K) -> list[dict]:
        """The passages worth giving the model: the best k that the reranker judges relevant."""
        return [
            {"document": hit["document"], "section": hit["section"], "snippet": hit["snippet"]}
            for hit in self.search(query, k)
            if hit["score"] >= RAG_RERANK_MIN_SCORE
        ]


_retriever: Retriever | None = None
_retriever_lock = threading.Lock()


def get_retriever() -> Retriever:
    """The shared retriever, created on first use."""
    global _retriever
    with _retriever_lock:
        if _retriever is None:
            _retriever = Retriever(ChromaStore.open(get_client()))
        return _retriever


def reset_retriever() -> None:
    """Forget the shared retriever, so the next use opens the store afresh."""
    global _retriever
    with _retriever_lock:
        _retriever = None


def warm_up() -> None:
    """Get the search ready before the first question. Never raises: a problem
    here is logged, and shows up as a normal error when a question needs it."""
    try:
        get_retriever().warm_up()
    except KnowledgeBaseNotFound as exc:
        logger.warning("%s Questions will be answered without campus documents until it is built.", exc)
    except Exception:
        logger.exception("Could not get the search ready")


def search(query: str, n: int) -> list[dict]:
    return get_retriever().search(query, n)


def retrieve(query: str, k: int = RAG_TOP_K) -> list[dict]:
    return get_retriever().retrieve(query, k)

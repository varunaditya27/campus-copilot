from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder

# A cross-encoder reads the question and a passage together, which is slower
# than comparing precomputed embeddings but far better at judging relevance.
# This one is small (about 80 MB) and runs on ONNX Runtime, so it needs no PyTorch.
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


@lru_cache
def _model() -> TextCrossEncoder:
    return TextCrossEncoder(model_name=RERANK_MODEL)


def rerank_scores(query: str, texts: list[str]) -> list[float]:
    """A relevance score for each text against the query. Higher is more relevant;
    the scores are only comparable within one call (and against a fixed threshold)."""
    if not texts:
        return []
    return [float(score) for score in _model().rerank(query, texts)]

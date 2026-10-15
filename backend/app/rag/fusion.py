# The constant from the original RRF paper (Cormack, Clarke and Buettcher, 2009).
RRF_K = 60


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Merge several best-first rankings of ids into one.

    Each id scores 1 / (k + rank) in every ranking it appears in, and the
    scores are added. Only ranks are used, never the raw scores, so rankings
    from methods whose scores cannot be compared (BM25 against vector
    distance) combine safely. An id that several rankings agree on rises.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)

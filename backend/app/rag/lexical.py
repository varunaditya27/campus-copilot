import re

import bm25s
from bm25s.stopwords import STOPWORDS_EN
from py_rust_stemmers import SnowballStemmer

_WORD = re.compile(r"[a-z0-9]+")
_STEMMER = SnowballStemmer("english")
_STOPWORDS = set(STOPWORDS_EN)


def tokenize(text: str) -> list[str]:
    """Lowercase words and numbers, minus stop-words, reduced to their stems, so
    "registered" and "registration" can match each other."""
    words = (w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS)
    return _STEMMER.stem_words(list(words))


class KeywordIndex:
    """BM25 keyword search over a list of texts. Positions refer to that list."""

    def __init__(self, texts: list[str]) -> None:
        self._size = len(texts)
        self._bm25 = bm25s.BM25()
        if texts:
            self._bm25.index([tokenize(t) for t in texts], show_progress=False)

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """(position, score) for the best matches, best first. Texts sharing no
        word with the query are left out."""
        tokens = tokenize(query)
        if not tokens or not self._size:
            return []
        positions, scores = self._bm25.retrieve([tokens], k=min(k, self._size), show_progress=False)
        return [(int(p), float(s)) for p, s in zip(positions[0], scores[0]) if s > 0]

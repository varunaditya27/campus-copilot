import pytest

from app.rag.fusion import reciprocal_rank_fusion
from app.rag.lexical import KeywordIndex, tokenize


def test_tokenize_lowercases_stems_and_keeps_numbers():
    assert tokenize("Courses REGISTERED, 75% attendance") == ["cours", "regist", "75", "attend"]


def test_tokenize_drops_stop_words():
    assert "the" not in tokenize("the library and the hostel")


def test_related_word_forms_meet_in_the_middle():
    assert tokenize("registering")[0] == tokenize("registered")[0]


def test_an_empty_or_symbols_only_query_has_no_tokens():
    assert tokenize("") == [] and tokenize("?!") == []


TEXTS = [
    "The library opens at eight in the morning",
    "Hostel mess serves dinner at half past seven",
    "A library fine of five rupees per day applies to late returns",
    "Dr. Geeta Nair teaches VLSI design in Room 305",
]


def test_keyword_search_ranks_the_best_match_first():
    index = KeywordIndex(TEXTS)
    positions = [p for p, _ in index.search("library fine", 4)]
    assert positions[0] == 2 and 0 in positions


def test_exact_names_and_numbers_are_found():
    index = KeywordIndex(TEXTS)
    assert index.search("Room 305", 3)[0][0] == 3
    assert index.search("Geeta Nair", 3)[0][0] == 3


def test_matching_ignores_word_form():
    assert KeywordIndex(TEXTS).search("fines returned", 3)[0][0] == 2


def test_texts_sharing_no_word_with_the_query_are_left_out():
    assert KeywordIndex(TEXTS).search("swimming pool", 4) == []


def test_k_limits_the_results_and_may_exceed_the_corpus():
    index = KeywordIndex(TEXTS)
    assert len(index.search("library", 1)) == 1
    assert len(index.search("library", 100)) <= len(TEXTS)


def test_an_empty_index_returns_nothing():
    assert KeywordIndex([]).search("anything", 5) == []


def test_scores_are_positive_and_sorted():
    scores = [s for _, s in KeywordIndex(TEXTS).search("library hostel", 4)]
    assert scores == sorted(scores, reverse=True) and all(s > 0 for s in scores)


# --- fusion


def ids(result):
    return [item for item, _ in result]


def test_an_item_both_rankings_like_beats_one_only_a_single_ranking_likes():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["c", "a", "d"]])
    assert ids(fused)[:2] == ["a", "c"]  # in both rankings
    assert set(ids(fused)) == {"a", "b", "c", "d"}


def test_a_single_ranking_keeps_its_order():
    assert ids(reciprocal_rank_fusion([["x", "y", "z"]])) == ["x", "y", "z"]


def test_scores_follow_the_formula():
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)


def test_rankings_that_disagree_completely_tie():
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "a"]]))
    assert fused["a"] == pytest.approx(fused["b"])


def test_a_smaller_k_favours_the_top_rank_and_a_larger_k_favours_agreement():
    # "top" is first in one ranking only; "both" is third and fourth in the two.
    rankings = [["top", "m", "n", "both"], ["x", "y", "both"]]
    assert ids(reciprocal_rank_fusion(rankings, k=1))[0] == "top"
    assert ids(reciprocal_rank_fusion(rankings, k=1000))[0] == "both"


def test_nothing_in_nothing_out():
    assert reciprocal_rank_fusion([]) == [] and reciprocal_rank_fusion([[], []]) == []

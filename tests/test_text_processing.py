from professor_fit_mcp.utils.text_processing import (
    whole_word_match,
    compute_keyword_overlap,
    flexible_phrase_match,
)


def test_flexible_phrase_match_word_order_independent():
    # word order in the keyword should not matter
    assert flexible_phrase_match("fairness order", "transaction order with fairness") is True


def test_flexible_phrase_match_hyphenated():
    # "order fairness" matches "Order-Fairness" (hyphen is a word boundary)
    assert flexible_phrase_match("order fairness", "Strong Order-Fairness in Byzantine Consensus") is True


def test_flexible_phrase_match_missing_word():
    # only one of the two words present -> no match
    assert flexible_phrase_match("order fairness", "fast transaction processing") is False


def test_flexible_phrase_match_single_word_strict():
    assert flexible_phrase_match("blockchain", "blockchain consensus") is True
    assert flexible_phrase_match("block", "blockchain consensus") is False


def test_whole_word_match_no_partial():
    # non-obvious: "block" must NOT match inside "blockchain"
    assert whole_word_match("block", "blockchain research") is False


def test_whole_word_match_case_insensitive():
    assert whole_word_match("Blockchain", "Recent BLOCKCHAIN work") is True


def test_compute_keyword_overlap_full():
    score = compute_keyword_overlap(
        keywords=["blockchain", "consensus"],
        corpus="blockchain consensus protocol research",
    )
    assert score == 1.0


def test_compute_keyword_overlap_partial():
    score = compute_keyword_overlap(
        keywords=["blockchain", "consensus", "MEV"],
        corpus="blockchain research and consensus",
    )
    assert abs(score - 2/3) < 0.01


def test_compute_keyword_overlap_empty_keywords():
    score = compute_keyword_overlap(keywords=[], corpus="anything")
    assert score == 0.0


def test_compute_keyword_overlap_empty_corpus():
    score = compute_keyword_overlap(keywords=["blockchain"], corpus="")
    assert score == 0.0

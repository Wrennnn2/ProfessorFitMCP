from professor_fit_mcp.utils.text_processing import whole_word_match, compute_keyword_overlap


def test_whole_word_match_found():
    assert whole_word_match("blockchain", "research on blockchain consensus") is True


def test_whole_word_match_not_found():
    assert whole_word_match("blockchain", "AI security and networking") is False


def test_whole_word_match_no_partial():
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

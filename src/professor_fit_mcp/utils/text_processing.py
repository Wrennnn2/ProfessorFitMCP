import re


def whole_word_match(keyword: str, text: str) -> bool:
    """Case-insensitive whole-word search. Avoids substring false positives."""
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return bool(re.search(pattern, text.lower()))


def compute_keyword_overlap(keywords: list[str], corpus: str) -> float:
    """Fraction of keywords found in corpus via whole-word matching. Returns 0.0 if keywords is empty."""
    if not keywords or not corpus:
        return 0.0
    matched = sum(1 for kw in keywords if whole_word_match(kw, corpus))
    return matched / len(keywords)

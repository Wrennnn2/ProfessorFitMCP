import re


def whole_word_match(keyword: str, text: str) -> bool:
    """Case-insensitive whole-word search. Avoids substring false positives."""
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return bool(re.search(pattern, text.lower()))


def flexible_phrase_match(keyword: str, text: str) -> bool:
    """
    Match a keyword against text with word-order flexibility.

    Single-word keywords use strict whole-word matching.
    Multi-word keywords (e.g. "order fairness") match when ALL constituent
    words appear independently in the text, regardless of order. This lets
    "order fairness" match "fair ordering of transactions".
    """
    words = keyword.lower().split()
    if len(words) <= 1:
        return whole_word_match(keyword, text)
    return all(whole_word_match(w, text) for w in words)


def compute_keyword_overlap(keywords: list[str], corpus: str) -> float:
    """Fraction of keywords found in corpus via flexible phrase matching. Returns 0.0 if keywords is empty."""
    if not keywords or not corpus:
        return 0.0
    matched = sum(1 for kw in keywords if flexible_phrase_match(kw, corpus))
    return matched / len(keywords)


def compute_weighted_overlap(
    topic_keywords: list[str],
    domain_keywords: list[str],
    corpus: str,
    topic_weight: float = 3.0,
    domain_weight: float = 1.0,
) -> float:
    """
    Weighted keyword overlap normalized to [0, 1].

    Topic hits contribute topic_weight each, domain hits domain_weight each,
    so a professor matching only domain terms scores much lower than one
    matching the core topic.
    """
    if not corpus:
        return 0.0
    max_score = topic_weight * len(topic_keywords) + domain_weight * len(domain_keywords)
    if max_score <= 0:
        return 0.0
    score = sum(
        topic_weight for kw in topic_keywords if flexible_phrase_match(kw, corpus)
    ) + sum(
        domain_weight for kw in domain_keywords if flexible_phrase_match(kw, corpus)
    )
    return score / max_score

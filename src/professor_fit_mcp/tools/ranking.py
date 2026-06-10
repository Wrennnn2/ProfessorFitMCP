from __future__ import annotations

from typing import Optional

from ..utils.text_processing import (
    compute_keyword_overlap,
    compute_weighted_overlap,
    flexible_phrase_match,
)

_PRESETS = {
    "blockchain_security": [
        "blockchain", "consensus", "MEV", "DeFi", "systems security",
        "distributed systems", "cryptography", "smart contracts",
    ],
    "ai_ml": [
        "machine learning", "deep learning", "NLP", "computer vision", "LLM",
        "foundation model", "reinforcement learning",
    ],
    "systems": [
        "operating systems", "distributed systems", "cloud", "storage",
        "networking", "databases", "architecture",
    ],
    "security": [
        "security", "privacy", "cryptography", "adversarial", "vulnerability",
        "malware", "authentication",
    ],
}

# Precision gating. Some terms are ambiguous across fields (e.g. "consensus" and
# "byzantine fault tolerance" appear in federated-learning and general distributed
# systems papers, not just blockchain). To keep results on-domain we gate on the
# domain's UNAMBIGUOUS core terms: a professor must match at least one of them.
#
# _DOMAIN_TRIGGERS detect which domain a search is about (from the user keywords).
# _DOMAIN_CORE_TERMS are the unambiguous anchors used as the precision gate.
_DOMAIN_TRIGGERS = {
    "blockchain": [
        "blockchain", "defi", "mev", "smart contract", "cryptocurrency", "web3",
        "consensus", "order fairness", "fair ordering", "transaction ordering",
        "frontrunning", "distributed ledger", "ethereum", "bitcoin",
    ],
}
_DOMAIN_CORE_TERMS = {
    "blockchain": [
        "blockchain", "blockchains", "DeFi", "decentralized finance", "MEV",
        "maximal extractable value", "smart contract", "smart contracts",
        "cryptocurrency", "web3", "distributed ledger", "on-chain", "Ethereum",
        "Bitcoin", "proof of stake", "proof of work", "rollup",
        "permissioned blockchain", "fair ordering", "order fairness",
        "DAG consensus", "blockchain consensus",
    ],
}


def derive_domain_anchors(keywords: list[str]) -> Optional[list[str]]:
    """
    If the search keywords clearly belong to a known domain, return that domain's
    unambiguous core terms to use as a precision anchor (ANY-match). Returns None
    when no domain is confidently detected.
    """
    blob = " ".join(keywords).lower()
    for domain, triggers in _DOMAIN_TRIGGERS.items():
        if any(t in blob for t in triggers):
            return _DOMAIN_CORE_TERMS[domain]
    return None


def _professor_corpus(professor: dict) -> str:
    """Concatenate concepts + recent paper titles/abstracts into one searchable string."""
    parts = list(professor.get("concepts") or [])
    for paper in professor.get("recent_papers") or []:
        if isinstance(paper, dict):
            parts.append(paper.get("title") or "")
            parts.append(paper.get("abstract") or "")
    return " ".join(parts)


def compute_professor_relevance(professor: dict, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    return compute_keyword_overlap(keywords, _professor_corpus(professor))


def _extract_keywords(user_interests: dict) -> list[str]:
    if "preset" in user_interests:
        preset_kws = _PRESETS.get(user_interests["preset"], [])
        extra = user_interests.get("keywords", [])
        return preset_kws + extra
    return user_interests.get("keywords", [])


def _apply_filters(professor: dict, filters: dict) -> bool:
    raw_citation = professor.get("citation_count")
    if isinstance(raw_citation, dict):
        citation = raw_citation.get("value") or 0
    else:
        citation = raw_citation or 0
    if filters.get("min_citation") and citation < filters["min_citation"]:
        return False
    if filters.get("regions"):
        allowed = {r.upper() for r in filters["regions"]}
        if professor.get("country_code", "").upper() not in allowed:
            return False
    if filters.get("institution_tier"):
        allowed_tiers = {t.upper() for t in filters["institution_tier"]}
        tier = (professor.get("institution_tier") or "").upper()
        if tier not in allowed_tiers:
            return False
    return True


async def rank_fit_impl(
    user_interests: dict,
    professors: list[dict],
    filters: Optional[dict] = None,
    sort_by: str = "relevance_signal",
) -> dict:
    keywords = _extract_keywords(user_interests)
    filters = filters or {}
    required_keywords = filters.get("required_keywords") or []
    min_relevance = filters.get("min_relevance", 0.0)

    # Weighted scoring: when the caller supplies a topic/domain split
    # (find_professors passes through intent analysis results), topic hits
    # score topic_weight each and domain hits domain_weight each, so the
    # search-stage keyword priority carries through to final ranking.
    topic_keywords = user_interests.get("topic_keywords") or []
    domain_keywords = user_interests.get("domain_keywords") or []
    topic_weight = float(user_interests.get("topic_weight", 3.0))
    domain_weight = float(user_interests.get("domain_weight", 1.0))
    use_weighted = bool(topic_keywords or domain_keywords)

    ranked = []
    for prof in professors:
        if not _apply_filters(prof, filters):
            continue

        corpus = _professor_corpus(prof)

        # Domain anchor: professor must mention AT LEAST ONE required keyword.
        # Pass a set of domain terms (e.g. ["blockchain", "DeFi", "consensus"])
        # to exclude off-domain false positives (e.g. "FAIR data" or "fair
        # allocation" papers) without dropping legitimate researchers who happen
        # to phrase the domain differently.
        if required_keywords and not any(
            flexible_phrase_match(rk, corpus) for rk in required_keywords
        ):
            continue

        if use_weighted:
            score = compute_weighted_overlap(
                topic_keywords, domain_keywords, corpus,
                topic_weight=topic_weight, domain_weight=domain_weight,
            )
        else:
            score = compute_keyword_overlap(keywords, corpus)
        if score < min_relevance:
            continue

        papers_summary = [
            {
                "title": p.get("title") if isinstance(p, dict) else p.title,
                "year": p.get("year") if isinstance(p, dict) else p.year,
                "abstract": (p.get("abstract") if isinstance(p, dict) else p.abstract) or "",
            }
            for p in (prof.get("recent_papers") or [])
        ]
        ranked.append({
            "professor": prof,
            "relevance_signal": round(score, 3),
            "fit_materials": {
                "user_interests": user_interests,
                "concepts": prof.get("concepts", []),
                "recent_papers_summary": papers_summary,
                "keywords_used": keywords,
            },
        })

    if sort_by == "citation":
        def _get_citation(x):
            c = x["professor"].get("citation_count")
            return c.get("value") or 0 if isinstance(c, dict) else c or 0
        ranked.sort(key=_get_citation, reverse=True)
    else:
        ranked.sort(key=lambda x: x["relevance_signal"], reverse=True)

    return {
        "ranked_professors": ranked,
        "total": len(ranked),
        "keywords_used": keywords,
        "sort_by": sort_by,
    }

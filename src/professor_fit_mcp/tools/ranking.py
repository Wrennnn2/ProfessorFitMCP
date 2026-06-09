from __future__ import annotations

from typing import Optional

from ..utils.text_processing import compute_keyword_overlap

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


def compute_professor_relevance(professor: dict, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    parts = list(professor.get("concepts") or [])
    for paper in professor.get("recent_papers") or []:
        if isinstance(paper, dict):
            parts.append(paper.get("title") or "")
            parts.append(paper.get("abstract") or "")
    corpus = " ".join(parts)
    return compute_keyword_overlap(keywords, corpus)


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

    ranked = []
    for prof in professors:
        if not _apply_filters(prof, filters):
            continue
        score = compute_professor_relevance(prof, keywords)
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

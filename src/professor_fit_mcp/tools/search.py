from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..services.openalex import OpenAlexService
from ..services.institution import InstitutionClassifier
from ..utils.cache import Cache

_cache: Optional[Cache] = None
_institution_clf: Optional[InstitutionClassifier] = None

_REGION_ALIASES = {
    "US": ["US"], "UK": ["GB"], "GB": ["GB"], "CN": ["CN"],
    "JP": ["JP"], "KR": ["KR"], "DE": ["DE"], "CA": ["CA"],
    "AU": ["AU"], "SG": ["SG"], "HK": ["HK"],
    "ASIA": ["CN", "JP", "KR", "SG", "HK", "TW"],
    "ALL": None,
}


def _get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(Path(os.getenv("PROFESSOR_FIT_CACHE_PATH", "professor_fit_cache.db")))
    return _cache


def _get_classifier() -> InstitutionClassifier:
    global _institution_clf
    if _institution_clf is None:
        _institution_clf = InstitutionClassifier()
    return _institution_clf


def _normalize_regions(regions: Optional[list[str]]) -> Optional[set[str]]:
    if not regions:
        return None
    codes: set[str] = set()
    for r in regions:
        expanded = _REGION_ALIASES.get(r.upper())
        if expanded is None:
            return None
        codes.update(expanded)
    return codes


async def search_professors_impl(
    keywords: list[str],
    paper_url: Optional[str] = None,
    regions: Optional[list[str]] = None,
    university_filter: Optional[list[str]] = None,
    institution_tier: Optional[list[str]] = None,
    limit: int = 20,
) -> dict:
    svc = OpenAlexService()
    cache = _get_cache()
    clf = _get_classifier()
    allowed_countries = _normalize_regions(regions)
    query = " ".join(keywords)

    cache_key = f"search:{query}:{limit}"
    cached = cache.get(cache_key, "professors")
    raw_results = cached if cached else await svc.search_authors(query, limit=limit * 2)
    if not cached:
        cache.set(cache_key, raw_results, "professors", ttl_seconds=Cache.PROFESSOR_TTL)

    professors = []
    for raw in raw_results:
        country = raw.get("country_code")
        if allowed_countries is not None and country not in allowed_countries:
            continue

        inst_name = raw.get("institution") or ""
        tier_info = clf.classify(inst_name, country)
        tier = tier_info.get("tier")

        if institution_tier and tier not in institution_tier:
            continue

        if university_filter:
            if not any(f.lower() in inst_name.lower() for f in university_filter):
                continue

        homepage_url = raw.get("homepage_url")
        search_query = None
        if not homepage_url:
            search_query = f"{raw['name']} {inst_name} homepage"

        prof = {
            "openalex_id": raw["openalex_id"],
            "name": raw["name"],
            "institution": inst_name,
            "country_code": country,
            "institution_tier": tier,
            "h_index": raw.get("h_index"),
            "citation_count": raw.get("citation_count"),
            "works_count": raw.get("works_count"),
            "papers_last_3_years": raw.get("papers_last_3_years"),
            "concepts": raw.get("concepts", []),
            "homepage_url": homepage_url,
            "homepage_search_query": search_query,
            "source": "openalex",
        }
        professors.append(prof)
        if len(professors) >= limit:
            break

    return {"professors": professors, "total_found": len(professors), "query": query}

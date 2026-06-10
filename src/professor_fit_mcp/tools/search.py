from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..services.openalex import OpenAlexService
from ..services.institution import InstitutionClassifier

_RECENT_AFFILIATION_WINDOW = 5  # years — wider window to catch recent faculty moves

_institution_clf: Optional[InstitutionClassifier] = None

_REGION_ALIASES = {
    "US": ["US"], "UK": ["GB"], "GB": ["GB"], "CN": ["CN"],
    "JP": ["JP"], "KR": ["KR"], "DE": ["DE"], "CA": ["CA"],
    "AU": ["AU"], "SG": ["SG"], "HK": ["HK"],
    "ASIA": ["CN", "JP", "KR", "SG", "HK", "TW"],
    "ALL": None,
}


def _get_classifier() -> InstitutionClassifier:
    global _institution_clf
    if _institution_clf is None:
        _institution_clf = InstitutionClassifier()
    return _institution_clf


def _resolve_region(raw: dict, allowed: Optional[set[str]]) -> tuple[bool, Optional[str], str]:
    """
    Decide whether an author belongs to the requested region, preferring recent
    affiliations over the often-stale last_known_institutions field.

    Resolution order:
      1. last_known_institutions country_code (fastest check)
      2. Per-year affiliations within the recent window
      3. Paper-level institutions (_paper_institutions) — most current, since
         OpenAlex author profiles can lag 1-2 years behind actual moves.

    Returns (matched, country_code, institution_name).
    """
    country = raw.get("country_code")
    inst_name = raw.get("institution") or ""

    if allowed is None:
        return True, country, inst_name
    if country in allowed:
        return True, country, inst_name

    # Check per-year affiliations
    cutoff = datetime.now().year - _RECENT_AFFILIATION_WINDOW
    recent_in_region = [
        a for a in (raw.get("affiliations") or [])
        if a.get("country_code") in allowed and (a.get("max_year") or 0) >= cutoff
    ]
    if recent_in_region:
        best = max(recent_in_region, key=lambda a: a.get("max_year") or 0)
        return True, best.get("country_code"), best.get("institution") or inst_name

    # Fallback: check paper-level institution data (enriched from works search).
    # This catches very recent moves that haven't propagated to the author profile.
    paper_insts = raw.get("_paper_institutions") or []
    for inst_tuple in paper_insts:
        if isinstance(inst_tuple, (list, tuple)) and len(inst_tuple) == 2:
            pi_name, pi_country = inst_tuple
            if pi_country in allowed:
                return True, pi_country, pi_name

    # Fallback: DBLP affiliation (human-curated, most accurate for current position).
    dblp_aff = raw.get("_dblp_affiliation") or ""
    if dblp_aff:
        clf = _get_classifier()
        tier_info = clf.classify(dblp_aff, None)
        dblp_country = tier_info.get("country")
        if dblp_country and dblp_country in allowed:
            return True, dblp_country, dblp_aff

    return False, country, inst_name


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
    since_year: Optional[int] = None,
    topic_keywords: Optional[list[str]] = None,
    domain_keywords: Optional[list[str]] = None,
    topic_weight: float = 3.0,
    domain_weight: float = 1.0,
) -> dict:
    svc = OpenAlexService()
    clf = _get_classifier()
    allowed_countries = _normalize_regions(regions)
    query = " ".join(keywords)

    effective_since = since_year or (datetime.now().year - 7)

    raw_results = await svc.search_works_authors(
        keywords, since_year=effective_since, limit=limit,
        country_codes=allowed_countries,
        topic_keywords=topic_keywords,
        domain_keywords=domain_keywords,
        topic_weight=topic_weight,
        domain_weight=domain_weight,
    )

    professors = []
    for raw in raw_results:
        matched, country, inst_name = _resolve_region(raw, allowed_countries)
        if not matched:
            continue

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

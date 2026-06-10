from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ..services.openalex import OpenAlexService
from ..services.dblp import DBLPService
from ..services.homepage import HomepageService
from ..services.institution import InstitutionClassifier
from ..models.professor import compute_seniority
from ..utils.profile_store import ProfileStore

_profile_store: Optional[ProfileStore] = None
_institution_clf: Optional[InstitutionClassifier] = None


def _get_profile_store() -> ProfileStore:
    global _profile_store
    if _profile_store is None:
        _profile_store = ProfileStore()
    return _profile_store


def _get_classifier() -> InstitutionClassifier:
    global _institution_clf
    if _institution_clf is None:
        _institution_clf = InstitutionClassifier()
    return _institution_clf


def _sourced(value, sources: list[str], confidence: str) -> dict:
    return {"value": value, "sources": sources, "confidence": confidence}


def _dedup_papers(papers: list) -> list:
    """Drop duplicate papers that share a normalized title (arXiv/conf/journal versions)."""
    seen_titles: set[str] = set()
    result = []
    for p in papers:
        title = (getattr(p, "title", "") or "").lower().strip()
        if not title:
            result.append(p)
            continue
        if title not in seen_titles:
            seen_titles.add(title)
            result.append(p)
    return result


async def get_professor_details_impl(
    professor_id: Optional[str] = None,
    name: Optional[str] = None,
    university: Optional[str] = None,
    hint_country: Optional[str] = None,
    hint_institution: Optional[str] = None,
    hint_tier: Optional[str] = None,
) -> dict:
    """
    hint_* values come from the search stage, which resolves the current
    institution from per-year affiliations (more reliable than OpenAlex's stale
    last_known_institutions). When provided they take precedence, so a professor
    who recently moved (e.g. last_known still says a former country) is reported
    at the correct current institution.
    """
    store = _get_profile_store()
    institution_clf = _get_classifier()

    oa_svc = OpenAlexService()
    if professor_id:
        oa_author = await oa_svc.get_author(professor_id)
    elif name:
        results = await oa_svc.search_authors(name, institution=university, limit=1)
        oa_author = results[0] if results else None
    else:
        raise ValueError("Must provide professor_id or name")

    if not oa_author:
        return {"error": "Professor not found in OpenAlex"}

    openalex_id = oa_author["openalex_id"]

    recent_papers = await oa_svc.get_recent_works(openalex_id, since_year=2023)
    recent_papers = _dedup_papers(recent_papers)

    dblp_svc = DBLPService()
    dblp_record = None
    search_name = oa_author.get("name", name or "")
    try:
        dblp_results = await dblp_svc.search_person(search_name, limit=3)
        if dblp_results:
            dblp_record = await dblp_svc.get_person_record(dblp_results[0]["pid"])
    except Exception:
        dblp_record = None

    homepage_url = None
    homepage_source = None
    if dblp_record and dblp_record.get("homepage_url"):
        homepage_url = dblp_record["homepage_url"]
        homepage_source = "dblp"
    elif oa_author.get("homepage_url"):
        homepage_url = oa_author["homepage_url"]
        homepage_source = "openalex"

    homepage_data = {
        "position": None, "email": None, "lab_name": None,
        "lab_url": None, "accepting_signal": None, "error": None,
    }
    if homepage_url:
        hp_svc = HomepageService()
        homepage_data = await hp_svc.fetch(homepage_url)

    country_code = oa_author.get("country_code")
    oa_inst = oa_author.get("institution") or ""
    dblp_affiliation = dblp_record.get("affiliation") if dblp_record else None

    # DBLP affiliation is curated and current; prefer it for display/classification
    # when OpenAlex's institution is missing or when we have a DBLP-verified value.
    inst_name = oa_inst or (dblp_affiliation or "")
    inst_sources = []
    if oa_inst:
        inst_sources.append("openalex")
    if dblp_affiliation:
        inst_sources.append("dblp")
    inst_confidence = "high" if (oa_inst and dblp_affiliation) else (
        "medium" if inst_name else "unknown"
    )
    tier_info = institution_clf.classify(inst_name, country_code)
    tier = tier_info.get("tier")

    # Search-stage hints (resolved from per-year affiliations) take precedence
    # over OpenAlex's stale last_known_institutions.
    if hint_institution:
        inst_name = hint_institution
        if "openalex_affiliations" not in inst_sources:
            inst_sources = ["openalex_affiliations"] + inst_sources
        inst_confidence = "high"
    if hint_country:
        country_code = hint_country
    if hint_tier is not None:
        tier = hint_tier

    first_pub_year = dblp_record.get("first_pub_year") if dblp_record else None
    seniority = compute_seniority(first_pub_year) if first_pub_year else None
    seniority_source = "dblp_estimate" if first_pub_year else "unknown"

    works_count = oa_author.get("works_count", 0) or 0
    inst_type = oa_author.get("institution_type", "")
    position_val = homepage_data.get("position")
    if position_val and "professor" in position_val.lower():
        is_pi_val, is_pi_conf = True, "high"
    elif works_count > 50 and inst_type == "education":
        is_pi_val, is_pi_conf = True, "medium"
    elif works_count > 20:
        is_pi_val, is_pi_conf = True, "low"
    else:
        is_pi_val, is_pi_conf = None, "unknown"

    dblp_pid = dblp_record["pid"] if dblp_record else None
    result = {
        "openalex_id": openalex_id,
        "dblp_pid": dblp_pid,
        "name": oa_author.get("name", ""),
        "institution": _sourced(inst_name, inst_sources, inst_confidence),
        "country_code": country_code,
        "institution_tier": tier,
        "position": _sourced(
            position_val,
            ["homepage"] if position_val else [],
            "medium" if position_val else "unknown",
        ),
        "is_pi": _sourced(
            is_pi_val,
            ["homepage" if position_val else "openalex_heuristic"],
            is_pi_conf,
        ),
        "h_index": _sourced(oa_author.get("h_index"), ["openalex"], "high"),
        "citation_count": _sourced(oa_author.get("citation_count"), ["openalex"], "high"),
        "works_count": oa_author.get("works_count"),
        "papers_last_3_years": oa_author.get("papers_last_3_years"),
        "first_pub_year": first_pub_year,
        "seniority": seniority,
        "seniority_source": seniority_source,
        "homepage_url": homepage_url,
        "homepage_source": homepage_source,
        "homepage_search_query": (
            f"{oa_author.get('name', '')} {inst_name} homepage" if not homepage_url else None
        ),
        "concepts": oa_author.get("concepts", []),
        "recent_papers": [p.model_dump() for p in recent_papers],
        "email": homepage_data.get("email"),
        "lab_name": homepage_data.get("lab_name"),
        "lab_url": homepage_data.get("lab_url"),
        "accepting_students_signal": homepage_data.get("accepting_signal"),
    }

    store.upsert_profile(result)
    return result

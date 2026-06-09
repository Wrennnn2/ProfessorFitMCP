import pytest
from professor_fit_mcp.tools.ranking import rank_fit_impl, compute_professor_relevance

_PROF_BLOCKCHAIN = {
    "openalex_id": "A1",
    "name": "Alice Smith",
    "institution": "MIT",
    "country_code": "US",
    "institution_tier": "R1",
    "h_index": {"value": 65, "sources": ["openalex"], "confidence": "high"},
    "citation_count": {"value": 18000, "sources": ["openalex"], "confidence": "high"},
    "concepts": ["Blockchain", "Consensus Protocols", "Distributed Systems"],
    "recent_papers": [
        {"title": "MEV in Blockchain", "year": 2024, "abstract": "We study MEV on blockchain", "source": "openalex"},
        {"title": "Fair Ordering", "year": 2023, "abstract": "blockchain consensus fairness", "source": "openalex"},
    ],
    "homepage_url": "https://alice.mit.edu",
}

_PROF_UNRELATED = {
    "openalex_id": "B2",
    "name": "Bob Jones",
    "institution": "Harvard",
    "country_code": "US",
    "institution_tier": "R1",
    "h_index": {"value": 90, "sources": ["openalex"], "confidence": "high"},
    "citation_count": {"value": 50000, "sources": ["openalex"], "confidence": "high"},
    "concepts": ["Immunology", "Genomics"],
    "recent_papers": [
        {"title": "CRISPR therapy", "year": 2024, "abstract": "gene editing study", "source": "openalex"},
    ],
    "homepage_url": None,
}


def test_compute_relevance_high():
    score = compute_professor_relevance(
        professor=_PROF_BLOCKCHAIN,
        keywords=["blockchain", "consensus", "MEV"],
    )
    assert score > 0.8


def test_compute_relevance_low():
    score = compute_professor_relevance(
        professor=_PROF_UNRELATED,
        keywords=["blockchain", "consensus", "MEV"],
    )
    assert score == 0.0


@pytest.mark.asyncio
async def test_rank_fit_sorts_by_relevance():
    result = await rank_fit_impl(
        user_interests={"keywords": ["blockchain", "consensus", "MEV"]},
        professors=[_PROF_UNRELATED, _PROF_BLOCKCHAIN],
    )
    profs = result["ranked_professors"]
    assert profs[0]["professor"]["openalex_id"] == "A1"
    assert profs[0]["relevance_signal"] > profs[1]["relevance_signal"]


@pytest.mark.asyncio
async def test_rank_fit_filter_min_citation():
    result = await rank_fit_impl(
        user_interests={"keywords": ["blockchain"]},
        professors=[_PROF_BLOCKCHAIN],
        filters={"min_citation": 999999},
    )
    assert len(result["ranked_professors"]) == 0


@pytest.mark.asyncio
async def test_rank_fit_returns_fit_materials():
    result = await rank_fit_impl(
        user_interests={"keywords": ["blockchain"], "description": "I study blockchain"},
        professors=[_PROF_BLOCKCHAIN],
    )
    prof_entry = result["ranked_professors"][0]
    assert "fit_materials" in prof_entry
    assert "concepts" in prof_entry["fit_materials"]
    assert "recent_papers_summary" in prof_entry["fit_materials"]

import pytest
from professor_fit_mcp.tools.ranking import (
    rank_fit_impl,
    compute_professor_relevance,
    derive_domain_anchors,
)


def test_derive_domain_anchors_blockchain():
    anchors = derive_domain_anchors(["blockchain", "order fairness", "MEV"])
    assert anchors is not None
    assert "blockchain" in anchors
    assert "DeFi" in anchors


def test_derive_domain_anchors_none_for_unknown():
    assert derive_domain_anchors(["protein folding", "genomics"]) is None


_PROF_FED_BYZANTINE = {
    "openalex_id": "C3",
    "name": "Carol Fed",
    "institution": "MIT",
    "country_code": "US",
    "institution_tier": "R1",
    "h_index": {"value": 40, "sources": ["openalex"], "confidence": "high"},
    "citation_count": {"value": 9000, "sources": ["openalex"], "confidence": "high"},
    "concepts": ["Machine learning", "Distributed optimization"],
    "recent_papers": [
        {"title": "Byzantine Fault-Tolerance in Federated Local SGD",
         "year": 2024, "abstract": "byzantine fault tolerance consensus in federated learning",
         "source": "openalex"},
    ],
    "homepage_url": None,
}


@pytest.mark.asyncio
async def test_precision_gate_excludes_fed_byzantine():
    # A federated-learning Byzantine-FT professor matches "byzantine"/"consensus"
    # but NOT blockchain core terms -> excluded by the auto-derived anchor.
    anchors = derive_domain_anchors(["blockchain", "consensus", "order fairness"])
    result = await rank_fit_impl(
        user_interests={"keywords": ["consensus", "byzantine fault tolerance"]},
        professors=[_PROF_FED_BYZANTINE, _PROF_BLOCKCHAIN],
        filters={"required_keywords": anchors},
    )
    ids = [p["professor"]["openalex_id"] for p in result["ranked_professors"]]
    assert "C3" not in ids          # fed-learning byzantine excluded
    assert "A1" in ids              # blockchain professor kept

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
async def test_rank_fit_required_keywords_excludes_off_domain():
    # require any of the domain set -> the immunology professor is dropped
    result = await rank_fit_impl(
        user_interests={"keywords": ["fairness", "consensus"]},
        professors=[_PROF_UNRELATED, _PROF_BLOCKCHAIN],
        filters={"required_keywords": ["blockchain", "DeFi", "consensus"]},
    )
    ids = [p["professor"]["openalex_id"] for p in result["ranked_professors"]]
    assert ids == ["A1"]


@pytest.mark.asyncio
async def test_rank_fit_required_keywords_any_match():
    # _PROF_BLOCKCHAIN has "blockchain" but not "quantum"; matching ANY keeps it
    result = await rank_fit_impl(
        user_interests={"keywords": ["consensus"]},
        professors=[_PROF_BLOCKCHAIN],
        filters={"required_keywords": ["quantum", "blockchain"]},
    )
    ids = [p["professor"]["openalex_id"] for p in result["ranked_professors"]]
    assert ids == ["A1"]


@pytest.mark.asyncio
async def test_rank_fit_min_relevance_threshold():
    # MEV-only keyword matches blockchain prof (1.0) but not unrelated (0.0);
    # threshold 0.5 keeps only the blockchain prof
    result = await rank_fit_impl(
        user_interests={"keywords": ["MEV"]},
        professors=[_PROF_UNRELATED, _PROF_BLOCKCHAIN],
        filters={"min_relevance": 0.5},
    )
    ids = [p["professor"]["openalex_id"] for p in result["ranked_professors"]]
    assert ids == ["A1"]


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

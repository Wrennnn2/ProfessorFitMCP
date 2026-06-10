import json

import pytest

from professor_fit_mcp.utils.profile_store import ProfileStore
from professor_fit_mcp.utils.profile_merger import ProfileMerger


SAMPLE_DETAILS = {
    "openalex_id": "A123",
    "dblp_pid": "46/0001",
    "name": "Alice Smith",
    "institution": {"value": "Stanford University", "sources": ["openalex"], "confidence": "high"},
    "country_code": "US",
    "institution_tier": "R1",
    "position": {"value": "Associate Professor", "sources": ["homepage"], "confidence": "medium"},
    "is_pi": {"value": True, "sources": ["homepage"], "confidence": "high"},
    "h_index": {"value": 85, "sources": ["openalex"], "confidence": "high"},
    "citation_count": {"value": 25000, "sources": ["openalex"], "confidence": "high"},
    "works_count": 150,
    "papers_last_3_years": 10,
    "first_pub_year": 2012,
    "seniority": "mid-career",
    "seniority_source": "dblp_estimate",
    "homepage_url": "https://cs.stanford.edu/~alice/",
    "homepage_source": "dblp",
    "homepage_search_query": None,
    "concepts": ["Machine Learning", "NLP"],
    "recent_papers": [
        {"title": "Test Paper", "year": 2024, "source": "openalex"},
    ],
    "email": "alice@cs.stanford.edu",
    "lab_name": "AI Lab",
    "lab_url": "https://ailab.stanford.edu",
    "accepting_students_signal": None,
}


@pytest.fixture
def store(tmp_path):
    return ProfileStore(db_path=tmp_path / "test_profiles.db")


# -- ProfileStore tests -------------------------------------------------------


def test_upsert_and_get_profile(store):
    store.upsert_profile(SAMPLE_DETAILS)
    profile = store.get_profile("A123")

    assert profile is not None
    assert profile["openalex_id"] == "A123"
    assert profile["name"] == "Alice Smith"
    assert profile["institution"] == "Stanford University"
    assert profile["country_code"] == "US"
    assert profile["institution_tier"] == "R1"
    assert profile["position"] == "Associate Professor"
    assert profile["is_pi"] == 1
    assert profile["h_index"] == 85
    assert profile["citation_count"] == 25000
    assert profile["homepage_url"] == "https://cs.stanford.edu/~alice/"
    assert profile["email"] == "alice@cs.stanford.edu"
    assert profile["seniority"] == "mid-career"
    concepts = json.loads(profile["concepts_json"])
    assert "Machine Learning" in concepts
    assert "NLP" in concepts


def test_upsert_updates_existing(store):
    store.upsert_profile(SAMPLE_DETAILS)
    original = store.get_profile("A123")
    created_at = original["created_at"]

    updated = {**SAMPLE_DETAILS, "name": "Alice J. Smith"}
    store.upsert_profile(updated)

    profile = store.get_profile("A123")
    assert profile["name"] == "Alice J. Smith"
    assert profile["created_at"] == created_at
    assert profile["updated_at"] >= original["updated_at"]


def test_get_profile_not_found(store):
    assert store.get_profile("NONEXISTENT") is None


def test_upsert_preserves_verified_and_manual_fields(store):
    """Re-upserting from a fresh search must NOT clobber manually verified data."""
    store.upsert_profile(SAMPLE_DETAILS)
    store.update_profile_fields("A123", {
        "homepage_url": "https://verified.example.com",
        "position": "Full Professor",
        "research_tags": ["fair ordering"],
        "manual_notes": "Manually confirmed via faculty page",
        "verification_status": "verified",
    })

    # Simulate the professor showing up in another search with stale data.
    stale = {**SAMPLE_DETAILS, "homepage_url": "https://stale.example.com",
             "position": {"value": "Assistant Professor", "sources": ["openalex"], "confidence": "low"},
             "h_index": {"value": 90, "sources": ["openalex"], "confidence": "high"}}
    store.upsert_profile(stale)

    profile = store.get_profile("A123")
    # Verified/manual fields survive.
    assert profile["homepage_url"] == "https://verified.example.com"
    assert profile["position"] == "Full Professor"
    assert profile["verification_status"] == "verified"
    assert profile["manual_notes"] == "Manually confirmed via faculty page"
    assert json.loads(profile["research_tags_json"]) == ["fair ordering"]
    # Dynamic metrics still refresh.
    assert profile["h_index"] == 90


def test_upsert_updates_identity_fields_while_unverified(store):
    store.upsert_profile(SAMPLE_DETAILS)
    updated = {**SAMPLE_DETAILS,
               "institution": {"value": "MIT", "sources": ["openalex"], "confidence": "high"}}
    store.upsert_profile(updated)

    profile = store.get_profile("A123")
    assert profile["institution"] == "MIT"
    assert profile["verification_status"] == "unverified"


def test_search_by_tag_exact_match_only(store):
    store.upsert_profile(SAMPLE_DETAILS)
    store.update_profile_fields("A123", {"research_tags": ["explainai", "ML"]})

    assert store.search_profiles(tag="explainai")
    # "ai" is a substring of "explainai" but not a stored tag.
    assert store.search_profiles(tag="ai") == []


def test_search_by_name(store):
    store.upsert_profile(SAMPLE_DETAILS)
    results = store.search_profiles(name="alice")
    assert len(results) >= 1
    assert any(r["openalex_id"] == "A123" for r in results)


def test_search_by_institution(store):
    store.upsert_profile(SAMPLE_DETAILS)
    results = store.search_profiles(institution="Stanford")
    assert len(results) >= 1
    assert results[0]["institution"] == "Stanford University"


def test_search_by_verification_status(store):
    store.upsert_profile(SAMPLE_DETAILS)
    results = store.search_profiles(verification_status="unverified")
    assert len(results) >= 1
    assert any(r["openalex_id"] == "A123" for r in results)


def test_list_all(store):
    store.upsert_profile(SAMPLE_DETAILS)
    second = {**SAMPLE_DETAILS, "openalex_id": "B456", "name": "Bob Jones"}
    store.upsert_profile(second)

    profiles = store.list_all()
    assert len(profiles) == 2
    ids = {p["openalex_id"] for p in profiles}
    assert ids == {"A123", "B456"}


def test_stats(store):
    store.upsert_profile(SAMPLE_DETAILS)
    second = {**SAMPLE_DETAILS, "openalex_id": "B456", "name": "Bob Jones"}
    store.upsert_profile(second)

    stats = store.stats()
    assert stats["total_profiles"] == 2


def test_add_and_get_evidence(store):
    store.upsert_profile(SAMPLE_DETAILS)

    evidence = {
        "openalex_id": "A123",
        "professor_key": "A123",
        "source_url": "https://cs.stanford.edu/people/alice",
        "source_type": "faculty_page",
        "extracted_json": {"institution": "Stanford University", "position": "Associate Professor"},
        "confidence": "high",
    }
    row_id = store.add_evidence(evidence)
    assert row_id is not None

    evidence_list = store.get_evidence("A123")
    assert len(evidence_list) >= 1
    assert evidence_list[0]["source_type"] == "faculty_page"
    assert evidence_list[0]["confidence"] == "high"


def test_update_profile_fields(store):
    store.upsert_profile(SAMPLE_DETAILS)

    success = store.update_profile_fields("A123", {
        "homepage_url": "https://new-homepage.example.com",
        "manual_notes": "Reviewed and confirmed",
    })
    assert success is True

    profile = store.get_profile("A123")
    assert profile["homepage_url"] == "https://new-homepage.example.com"
    assert profile["manual_notes"] == "Reviewed and confirmed"


def test_update_nonexistent_profile(store):
    result = store.update_profile_fields("UNKNOWN_ID", {"homepage_url": "https://example.com"})
    assert result is False


def test_export_profiles_json(store):
    store.upsert_profile(SAMPLE_DETAILS)

    exported = store.export_profiles(format="json")
    data = json.loads(exported)

    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["openalex_id"] == "A123"
    assert data[0]["name"] == "Alice Smith"


# -- ProfileMerger tests ------------------------------------------------------


def test_merge_adds_homepage_from_evidence():
    profile = {
        "openalex_id": "A123",
        "name": "Alice Smith",
        "homepage_url": None,
        "institution": "Stanford University",
        "concepts_json": json.dumps(["Machine Learning"]),
        "recent_papers_json": json.dumps([]),
        "verification_status": "unverified",
    }
    evidence = [
        {
            "source_type": "faculty_page",
            "confidence": "high",
            "extracted_json": {"homepage_url": "https://cs.stanford.edu/~alice/"},
        },
    ]

    merged = ProfileMerger.merge_evidence_into_profile(profile, evidence)
    assert merged["homepage_url"] == "https://cs.stanford.edu/~alice/"


def test_merge_higher_priority_wins():
    profile = {
        "openalex_id": "A123",
        "name": "Alice Smith",
        "homepage_url": "https://openalex.example.com/alice",
        "homepage_source": "openalex",
        "institution": "Stanford University",
        "concepts_json": json.dumps([]),
        "recent_papers_json": json.dumps([]),
        "verification_status": "unverified",
    }
    evidence = [
        {
            "source_type": "faculty_page",
            "confidence": "high",
            "extracted_json": {"homepage_url": "https://cs.stanford.edu/~alice/"},
        },
    ]

    merged = ProfileMerger.merge_evidence_into_profile(profile, evidence)
    assert merged["homepage_url"] == "https://cs.stanford.edu/~alice/"


def test_merge_detects_institution_conflict():
    profile = {
        "openalex_id": "A123",
        "name": "Alice Smith",
        "homepage_url": None,
        "institution": "Stanford University",
        "concepts_json": json.dumps([]),
        "recent_papers_json": json.dumps([]),
        "verification_status": "unverified",
    }
    evidence = [
        {
            "source_type": "faculty_page",
            "confidence": "high",
            "extracted_json": {"institution": "MIT"},
        },
    ]

    merged = ProfileMerger.merge_evidence_into_profile(profile, evidence)
    conflicts = json.loads(merged["conflicts_json"])
    assert "institution" in conflicts
    assert merged["verification_status"] in ("needs_review", "verified")


def test_merge_verified_when_sources_agree():
    profile = {
        "openalex_id": "A123",
        "name": "Alice Smith",
        "homepage_url": None,
        "institution": "Stanford University",
        "concepts_json": json.dumps([]),
        "recent_papers_json": json.dumps([]),
        "verification_status": "unverified",
    }
    evidence = [
        {
            "source_type": "faculty_page",
            "confidence": "high",
            "extracted_json": {"institution": "Stanford University"},
        },
    ]

    merged = ProfileMerger.merge_evidence_into_profile(profile, evidence)
    assert merged["verification_status"] == "verified"


def test_merge_research_tags_deduped():
    profile = {
        "openalex_id": "A123",
        "name": "Alice Smith",
        "homepage_url": None,
        "institution": "Stanford University",
        "concepts_json": json.dumps(["NLP", "Machine Learning"]),
        "recent_papers_json": json.dumps([]),
        "verification_status": "unverified",
    }
    evidence = [
        {
            "source_type": "faculty_page",
            "confidence": "high",
            "extracted_json": {"research_tags": ["Machine Learning", "Deep Learning"]},
        },
    ]

    merged = ProfileMerger.merge_evidence_into_profile(profile, evidence)
    tags = json.loads(merged["research_tags_json"])
    assert "Deep Learning" in tags
    assert "Machine Learning" in tags
    assert "NLP" in tags
    assert len(tags) == len(set(t.lower() for t in tags))


def test_merge_unverified_with_weak_evidence():
    profile = {
        "openalex_id": "A123",
        "name": "Alice Smith",
        "homepage_url": None,
        "institution": "Stanford University",
        "concepts_json": json.dumps([]),
        "recent_papers_json": json.dumps([]),
        "verification_status": "unverified",
    }
    evidence = [
        {
            "source_type": "other",
            "confidence": "low",
            "extracted_json": {"institution": "Stanford University"},
        },
    ]

    merged = ProfileMerger.merge_evidence_into_profile(profile, evidence)
    assert merged["verification_status"] == "unverified"

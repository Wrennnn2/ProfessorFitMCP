import pytest
from unittest.mock import AsyncMock, patch
from professor_fit_mcp.tools.details import get_professor_details_impl
import professor_fit_mcp.tools.details as details_mod


@pytest.fixture(autouse=True)
def _reset_store(tmp_path):
    details_mod._profile_store = None
    details_mod._institution_clf = None
    import os
    os.environ["PROFESSOR_PROFILES_DB_PATH"] = str(tmp_path / "test_profiles.db")
    yield
    details_mod._profile_store = None
    details_mod._institution_clf = None
    os.environ.pop("PROFESSOR_PROFILES_DB_PATH", None)


@pytest.mark.asyncio
async def test_details_from_openalex_and_dblp():
    openalex_author = {
        "openalex_id": "A123",
        "name": "Alice Smith",
        "institution": "Stanford University",
        "country_code": "US",
        "institution_type": "education",
        "h_index": 85,
        "citation_count": 25000,
        "works_count": 150,
        "papers_last_3_years": 10,
        "concepts": ["Machine Learning", "NLP"],
        "homepage_url": None,
    }
    dblp_search = [{"pid": "46/0001", "name": "Alice Smith", "dblp_url": "..."}]
    dblp_record = {
        "pid": "46/0001",
        "homepage_url": "https://cs.stanford.edu/~alice/",
        "first_pub_year": 2012,
    }
    homepage_data = {
        "position": "Associate Professor",
        "email": "alice@cs.stanford.edu",
        "lab_name": "AI Lab",
        "lab_url": "https://ailab.stanford.edu",
        "accepting_signal": None,
        "error": None,
    }

    from professor_fit_mcp.models.paper import Paper
    recent_papers = [
        Paper(title="Test Paper", year=2024, source="openalex")
    ]

    with (
        patch("professor_fit_mcp.tools.details.OpenAlexService.get_author",
              new=AsyncMock(return_value=openalex_author)),
        patch("professor_fit_mcp.tools.details.OpenAlexService.get_recent_works",
              new=AsyncMock(return_value=recent_papers)),
        patch("professor_fit_mcp.tools.details.DBLPService.search_person",
              new=AsyncMock(return_value=dblp_search)),
        patch("professor_fit_mcp.tools.details.DBLPService.get_person_record",
              new=AsyncMock(return_value=dblp_record)),
        patch("professor_fit_mcp.tools.details.HomepageService.fetch",
              new=AsyncMock(return_value=homepage_data)),
    ):
        result = await get_professor_details_impl(professor_id="A123")

    assert result["openalex_id"] == "A123"
    assert result["name"] == "Alice Smith"
    assert result["h_index"]["value"] == 85
    assert result["h_index"]["sources"] == ["openalex"]
    assert result["h_index"]["confidence"] == "high"
    assert result["position"]["value"] == "Associate Professor"
    assert result["position"]["sources"] == ["homepage"]
    assert result["homepage_url"] == "https://cs.stanford.edu/~alice/"
    assert result["homepage_source"] == "dblp"
    assert result["seniority"] == "mid-career"  # 2026 - 2012 = 14 years
    assert result["email"] == "alice@cs.stanford.edu"
    assert result["institution_tier"] == "R1"


@pytest.mark.asyncio
async def test_details_not_found():
    with patch(
        "professor_fit_mcp.tools.details.OpenAlexService.get_author",
        new=AsyncMock(return_value=None),
    ):
        result = await get_professor_details_impl(professor_id="UNKNOWN")

    assert result["error"] == "Professor not found in OpenAlex"


@pytest.mark.asyncio
async def test_details_no_dblp_match():
    openalex_author = {
        "openalex_id": "B456",
        "name": "Bob Jones",
        "institution": "Unknown University",
        "country_code": "US",
        "institution_type": "education",
        "h_index": 10,
        "citation_count": 500,
        "works_count": 15,
        "papers_last_3_years": 3,
        "concepts": ["Biology"],
        "homepage_url": None,
    }

    with (
        patch("professor_fit_mcp.tools.details.OpenAlexService.get_author",
              new=AsyncMock(return_value=openalex_author)),
        patch("professor_fit_mcp.tools.details.OpenAlexService.get_recent_works",
              new=AsyncMock(return_value=[])),
        patch("professor_fit_mcp.tools.details.DBLPService.search_person",
              new=AsyncMock(return_value=[])),
    ):
        result = await get_professor_details_impl(professor_id="B456")

    assert result["openalex_id"] == "B456"
    assert result["dblp_pid"] is None
    assert result["homepage_url"] is None
    assert result["seniority"] is None
    assert result["seniority_source"] == "unknown"
    assert result["is_pi"]["value"] is None
    assert result["is_pi"]["confidence"] == "unknown"


@pytest.mark.asyncio
async def test_details_homepage_from_openalex():
    openalex_author = {
        "openalex_id": "C789",
        "name": "Carol Lee",
        "institution": "Massachusetts Institute of Technology",
        "country_code": "US",
        "institution_type": "education",
        "h_index": 50,
        "citation_count": 12000,
        "works_count": 80,
        "papers_last_3_years": 5,
        "concepts": ["Robotics"],
        "homepage_url": "https://mit.edu/~carol",
    }
    dblp_search = [{"pid": "99/0001", "name": "Carol Lee", "dblp_url": "..."}]
    dblp_record = {
        "pid": "99/0001",
        "homepage_url": None,
        "first_pub_year": 2000,
    }
    homepage_data = {
        "position": "Full Professor",
        "email": "carol@mit.edu",
        "lab_name": "Robotics Lab",
        "lab_url": "https://robotics.mit.edu",
        "accepting_signal": None,
        "error": None,
    }

    with (
        patch("professor_fit_mcp.tools.details.OpenAlexService.get_author",
              new=AsyncMock(return_value=openalex_author)),
        patch("professor_fit_mcp.tools.details.OpenAlexService.get_recent_works",
              new=AsyncMock(return_value=[])),
        patch("professor_fit_mcp.tools.details.DBLPService.search_person",
              new=AsyncMock(return_value=dblp_search)),
        patch("professor_fit_mcp.tools.details.DBLPService.get_person_record",
              new=AsyncMock(return_value=dblp_record)),
        patch("professor_fit_mcp.tools.details.HomepageService.fetch",
              new=AsyncMock(return_value=homepage_data)),
    ):
        result = await get_professor_details_impl(professor_id="C789")

    assert result["homepage_url"] == "https://mit.edu/~carol"
    assert result["homepage_source"] == "openalex"
    assert result["seniority"] == "senior"  # 2026 - 2000 = 26 years
    assert result["is_pi"]["value"] is True
    assert result["is_pi"]["confidence"] == "high"
    assert result["institution_tier"] == "R1"


@pytest.mark.asyncio
async def test_details_requires_id_or_name():
    with pytest.raises(ValueError, match="Must provide professor_id or name"):
        await get_professor_details_impl()


@pytest.mark.asyncio
async def test_details_search_by_name():
    openalex_author = {
        "openalex_id": "D001",
        "name": "Dave Park",
        "institution": "Seoul National University",
        "country_code": "KR",
        "institution_type": "education",
        "h_index": 30,
        "citation_count": 4000,
        "works_count": 60,
        "papers_last_3_years": 7,
        "concepts": ["NLP"],
        "homepage_url": None,
    }

    with (
        patch("professor_fit_mcp.tools.details.OpenAlexService.search_authors",
              new=AsyncMock(return_value=[openalex_author])),
        patch("professor_fit_mcp.tools.details.OpenAlexService.get_recent_works",
              new=AsyncMock(return_value=[])),
        patch("professor_fit_mcp.tools.details.DBLPService.search_person",
              new=AsyncMock(return_value=[])),
    ):
        result = await get_professor_details_impl(name="Dave Park", university="Seoul National")

    assert result["openalex_id"] == "D001"
    assert result["name"] == "Dave Park"
    assert result["is_pi"]["value"] is True
    assert result["is_pi"]["confidence"] == "medium"

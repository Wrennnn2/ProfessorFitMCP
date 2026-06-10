import pytest
from unittest.mock import AsyncMock, patch
from professor_fit_mcp.tools.search import search_professors_impl
import professor_fit_mcp.tools.search as search_mod


@pytest.fixture(autouse=True)
def _reset(tmp_path):
    search_mod._institution_clf = None
    yield
    search_mod._institution_clf = None


@pytest.fixture
def mock_openalex_results():
    return [
        {
            "openalex_id": "A123",
            "name": "Alice Smith",
            "institution": "Massachusetts Institute of Technology",
            "country_code": "US",
            "institution_type": "education",
            "h_index": 65,
            "citation_count": 18000,
            "works_count": 120,
            "papers_last_3_years": 12,
            "concepts": ["Machine Learning", "Blockchain"],
            "homepage_url": None,
        }
    ]


@pytest.mark.asyncio
async def test_search_returns_professors(mock_openalex_results):
    with patch(
        "professor_fit_mcp.tools.search.OpenAlexService.search_works_authors",
        new=AsyncMock(return_value=mock_openalex_results),
    ):
        result = await search_professors_impl(
            keywords=["blockchain", "machine learning"],
            limit=10,
        )
    assert len(result["professors"]) == 1
    prof = result["professors"][0]
    assert prof["openalex_id"] == "A123"
    assert prof["name"] == "Alice Smith"
    assert prof["institution_tier"] == "R1"


@pytest.mark.asyncio
async def test_search_adds_homepage_search_query(mock_openalex_results):
    with patch(
        "professor_fit_mcp.tools.search.OpenAlexService.search_works_authors",
        new=AsyncMock(return_value=mock_openalex_results),
    ):
        result = await search_professors_impl(keywords=["blockchain"])
    prof = result["professors"][0]
    assert prof["homepage_url"] is None
    assert "Alice Smith" in prof["homepage_search_query"]
    assert "Massachusetts" in prof["homepage_search_query"] or "MIT" in prof["homepage_search_query"]


@pytest.mark.asyncio
async def test_search_region_filter():
    cn_result = [{
        "openalex_id": "B456",
        "name": "Bob Zhang",
        "institution": "Tsinghua University",
        "country_code": "CN",
        "institution_type": "education",
        "h_index": 40,
        "citation_count": 5000,
        "works_count": 80,
        "papers_last_3_years": 8,
        "concepts": ["Blockchain"],
        "homepage_url": None,
    }]
    with patch(
        "professor_fit_mcp.tools.search.OpenAlexService.search_works_authors",
        new=AsyncMock(return_value=cn_result),
    ):
        result = await search_professors_impl(
            keywords=["blockchain"],
            regions=["US"],
        )
    assert len(result["professors"]) == 0

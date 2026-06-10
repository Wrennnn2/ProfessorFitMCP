import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

from professor_fit_mcp.tools.find import find_professors_impl


_SEARCH_RESULT = {
    "professors": [
        {"openalex_id": "A1", "name": "Alice Smith", "institution": "MIT",
         "country_code": "US", "institution_tier": "R1", "h_index": 65,
         "citation_count": 18000, "concepts": ["Blockchain"], "homepage_url": None},
    ],
    "total_found": 1,
    "query": "blockchain",
}

_DETAIL = {
    "openalex_id": "A1",
    "name": "Alice Smith",
    "institution": {"value": "MIT", "sources": ["openalex"], "confidence": "high"},
    "country_code": "US",
    "institution_tier": "R1",
    "h_index": {"value": 65, "sources": ["openalex"], "confidence": "high"},
    "citation_count": {"value": 18000, "sources": ["openalex"], "confidence": "high"},
    "seniority": "mid-career",
    "concepts": ["Blockchain", "Consensus"],
    "recent_papers": [
        {"title": "Order-Fairness in Consensus", "year": 2024,
         "abstract": "blockchain order fairness", "source": "openalex"},
    ],
    "homepage_url": "https://alice.mit.edu",
}


def test_find_professors_end_to_end(tmp_path):
    out = str(tmp_path / "out.md")

    async def _run():
        with (
            patch("professor_fit_mcp.tools.find.search_professors_impl",
                  new=AsyncMock(return_value=_SEARCH_RESULT)),
            patch("professor_fit_mcp.tools.find.get_professor_details_impl",
                  new=AsyncMock(return_value=_DETAIL)),
        ):
            result = await find_professors_impl(
                keywords=["blockchain", "order fairness"], output_path=out
            )

        assert result["total"] == 1
        assert "Alice Smith" in result["markdown"]
        # homepage rendered as a clickable link
        assert "[link](https://alice.mit.edu)" in result["markdown"]
        # top paper title appears
        assert "Order-Fairness in Consensus" in result["markdown"]
        assert result["ranked_professors"][0]["professor"]["openalex_id"] == "A1"

    asyncio.run(_run())


def test_find_professors_auto_saves_markdown(tmp_path):
    # No output_path -> a file is auto-generated under PROFESSOR_FIT_OUTPUT_DIR
    async def _run():
        with (
            patch.dict(os.environ, {"PROFESSOR_FIT_OUTPUT_DIR": str(tmp_path)}),
            patch("professor_fit_mcp.tools.find.search_professors_impl",
                  new=AsyncMock(return_value=_SEARCH_RESULT)),
            patch("professor_fit_mcp.tools.find.get_professor_details_impl",
                  new=AsyncMock(return_value=_DETAIL)),
        ):
            result = await find_professors_impl(keywords=["blockchain", "order fairness"])

        saved = result["saved_to"]
        assert saved is not None
        assert Path(saved).exists()
        assert Path(saved).name.startswith("professor_fit_")
        assert Path(saved).suffix == ".md"
        assert "Alice Smith" in Path(saved).read_text(encoding="utf-8")

    asyncio.run(_run())


def test_find_professors_skips_failed_details(tmp_path):
    async def _run():
        with (
            patch("professor_fit_mcp.tools.find.search_professors_impl",
                  new=AsyncMock(return_value=_SEARCH_RESULT)),
            patch("professor_fit_mcp.tools.find.get_professor_details_impl",
                  new=AsyncMock(return_value={"error": "not found"})),
        ):
            result = await find_professors_impl(
                keywords=["blockchain"], output_path=str(tmp_path / "o.md")
            )

        # detail failed -> professor skipped, no crash
        assert result["total"] == 0

    asyncio.run(_run())

"""
Professor Fit MCP Server

Helps PhD applicants find matching professors.
Input: research interests (keywords / paper URL)
Output: structured professor data with provenance for client LLM fit judgment.

CLIENT LLM RUBRIC (for rank_fit results):
- HIGH fit: professor's recent papers directly address user's core keywords; multiple concept overlaps.
- MEDIUM fit: related area with some overlap but not primary focus.
- LOW fit: tangential or older work in the area.
For each professor, produce: fit_level, match_reasons (list), potential_concerns (list), email_advice.
"""
from mcp.server.fastmcp import FastMCP
from typing import Optional

from .tools.search import search_professors_impl
from .tools.details import get_professor_details_impl
from .tools.ranking import rank_fit_impl
from .tools.export import export_table_impl

mcp = FastMCP("professor-fit")


@mcp.tool()
async def search_professors(
    keywords: list[str],
    paper_url: Optional[str] = None,
    regions: Optional[list[str]] = None,
    university_filter: Optional[list[str]] = None,
    institution_tier: Optional[list[str]] = None,
    limit: int = 20,
) -> dict:
    """
    Search for professors matching research interests (coarse filter).

    Args:
        keywords: Research interest keywords, e.g. ["blockchain", "consensus", "MEV"]
        paper_url: Optional arXiv/DOI URL to extract keywords from
        regions: Country/region codes to filter by, e.g. ["US", "UK", "CN"].
                 Supported: US, UK/GB, CN, JP, KR, DE, CA, AU, SG, HK, ASIA, ALL
        university_filter: Specific university names to include
        institution_tier: Filter by tier, e.g. ["R1", "Russell", "985"]
        limit: Max number of results (default 20)

    Returns:
        dict with "professors" list and "total_found". Each professor includes
        openalex_id, name, institution, country_code, institution_tier, h_index,
        citation_count, concepts, homepage_url (or homepage_search_query for client fallback).
    """
    return await search_professors_impl(
        keywords=keywords, paper_url=paper_url, regions=regions,
        university_filter=university_filter, institution_tier=institution_tier, limit=limit,
    )


@mcp.tool()
async def get_professor_details(
    professor_id: Optional[str] = None,
    name: Optional[str] = None,
    university: Optional[str] = None,
) -> dict:
    """
    Get detailed multi-source profile for a professor.

    Fetches from OpenAlex (metrics, concepts, recent papers) + DBLP (homepage URL,
    first publication year) + homepage (position, email, lab, accepting students signal).
    All key fields include source and confidence metadata.

    Args:
        professor_id: OpenAlex author ID (preferred), e.g. "A5023888391"
        name: Professor's name (used if professor_id not provided)
        university: University name to disambiguate when searching by name

    Returns:
        Full professor profile with sourced fields (value/sources/confidence),
        recent papers (last 3 years), seniority estimate, and accepting_students_signal.
        If homepage_url is null, homepage_search_query is provided for client web search.
    """
    return await get_professor_details_impl(
        professor_id=professor_id, name=name, university=university,
    )


@mcp.tool()
async def rank_fit(
    user_interests: dict,
    professors: list[dict],
    filters: Optional[dict] = None,
    sort_by: str = "relevance_signal",
) -> dict:
    """
    Rank professors by keyword overlap and package materials for client LLM fit judgment.

    SERVER SIDE: Deterministic whole-word keyword matching against concepts + paper titles/abstracts.
    CLIENT SIDE: Use the fit_materials in each result to produce fit_level, match_reasons,
    potential_concerns, and email_advice.

    Args:
        user_interests: Dict with one of:
          - {"keywords": ["blockchain", "MEV"]}
          - {"preset": "blockchain_security"}
          - {"keywords": [...], "description": "free text", "paper_urls": [...]}
        professors: List from search_professors or get_professor_details
        filters: Optional: min_citation (int), regions (list), institution_tier (list)
        sort_by: "relevance_signal" (default) | "citation"

    Returns:
        ranked_professors list with relevance_signal and fit_materials for client LLM.
    """
    return await rank_fit_impl(
        user_interests=user_interests, professors=professors,
        filters=filters, sort_by=sort_by,
    )


@mcp.tool()
async def export_table(
    professors: list[dict],
    format: str = "markdown",
    include_summary: bool = True,
    output_path: Optional[str] = None,
) -> dict:
    """
    Export ranked professors as a formatted table.

    Args:
        professors: ranked_professors list from rank_fit
        format: "markdown" (default) | "csv" | "json"
        include_summary: Include count summary (default True)
        output_path: Optional file path to save output

    Returns:
        dict with "content" (string), "format", and "saved_to" (path if saved).
    """
    return export_table_impl(
        professors=professors, format=format,
        include_summary=include_summary, output_path=output_path,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()

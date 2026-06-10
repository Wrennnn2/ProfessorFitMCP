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
from .tools.find import find_professors_impl
from .tools.profiles import (
    update_professor_profile_impl,
    add_web_search_evidence_impl,
    profiles_inspect_impl,
    profiles_export_impl,
)

mcp = FastMCP("professor-fit")


@mcp.tool()
async def find_professors(
    keywords: list[str],
    regions: Optional[list[str]] = None,
    institution_tier: Optional[list[str]] = None,
    required_keywords: Optional[list[str]] = None,
    min_relevance: float = 0.0,
    limit: int = 10,
    output_path: Optional[str] = None,
    since_year: Optional[int] = None,
    topic_keywords: Optional[list[str]] = None,
    domain_keywords: Optional[list[str]] = None,
    topic_weight: float = 3.0,
    domain_weight: float = 1.0,
) -> dict:
    """
    One-shot professor finder (RECOMMENDED entry point).

    Runs the full pipeline in a single call: search candidates -> fetch
    multi-source details (concurrently) -> rank by relevance -> render a
    Markdown table.

    KEYWORD PRIORITY (IMPORTANT):
        For precise results, split your query into topic vs domain:
        - topic_keywords: The specific research problem the professor MUST work on.
          These get scored with topic_weight (default 3x). Include synonym phrasings.
          Example: ["order fairness", "fair ordering", "fair transaction ordering"]
        - domain_keywords: The broader field/area (used as context/filter, lower weight).
          Example: ["blockchain", "DeFi", "decentralized finance"]

        If you only provide `keywords` without topic/domain split, the server will
        attempt to auto-analyze intent (via LLM if configured, else heuristics).

    Args:
        keywords: Research interest keywords (flat list, backward-compatible).
        topic_keywords: Core research topic terms. Professors MUST work on this.
                 Receives topic_weight scoring boost. Include 2-4 synonym phrasings.
        domain_keywords: Broader field/area terms. Used as context filter.
                 Receives domain_weight scoring (lower than topic).
        topic_weight: Score multiplier for topic query hits (default 3.0).
        domain_weight: Score multiplier for domain query hits (default 1.0).
        regions: Country/region codes. Supported: US, UK/GB, JP, KR, DE, CA, AU, SG, HK, ASIA, ALL
        institution_tier: Filter by tier, e.g. ["R1", "Russell", "HK5"]
        required_keywords: Domain-anchor terms for precision gating.
        min_relevance: Minimum relevance score (0.0-1.0) to keep a professor.
        limit: Max number of professors (default 10).
        output_path: Path to save Markdown. Auto-generated if omitted.
        since_year: Only papers from this year onward (default: current_year - 7).

    Returns:
        dict with markdown, ranked_professors, total, saved_to, homepage_resolution.
    """
    return await find_professors_impl(
        keywords=keywords,
        regions=regions,
        institution_tier=institution_tier,
        required_keywords=required_keywords,
        min_relevance=min_relevance,
        limit=limit,
        output_path=output_path,
        since_year=since_year,
        topic_keywords=topic_keywords,
        domain_keywords=domain_keywords,
        topic_weight=topic_weight,
        domain_weight=domain_weight,
    )


@mcp.tool()
async def search_professors(
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
    """
    Search for professors matching research interests (coarse filter).

    Args:
        keywords: Research interest keywords (flat list).
        topic_keywords: Core topic terms (high scoring weight). See find_professors.
        domain_keywords: Broader field terms (lower scoring weight).
        topic_weight: Multiplier for topic hits (default 3.0).
        domain_weight: Multiplier for domain hits (default 1.0).
        paper_url: Optional arXiv/DOI URL to extract keywords from.
        regions: Country/region codes. Supported: US, UK/GB, JP, KR, DE, CA, AU, SG, HK, ASIA, ALL
        university_filter: Specific university names to include.
        institution_tier: Filter by tier, e.g. ["R1", "Russell", "HK5"]
        limit: Max number of results (default 20).
        since_year: Only papers from this year onward (default: current_year - 7).

    Returns:
        dict with "professors" list and "total_found".
    """
    return await search_professors_impl(
        keywords=keywords, paper_url=paper_url, regions=regions,
        university_filter=university_filter, institution_tier=institution_tier,
        limit=limit, since_year=since_year,
        topic_keywords=topic_keywords, domain_keywords=domain_keywords,
        topic_weight=topic_weight, domain_weight=domain_weight,
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
          Optionally add topic/domain weighting (same semantics as find_professors):
          - {"topic_keywords": [...], "domain_keywords": [...],
             "topic_weight": 3.0, "domain_weight": 1.0}
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


@mcp.tool()
async def update_professor_profile(
    openalex_id: str,
    homepage_url: Optional[str] = None,
    position: Optional[str] = None,
    is_pi: Optional[bool] = None,
    pi_verification_source: Optional[str] = None,
    homepage_verification_source: Optional[str] = None,
    institution: Optional[str] = None,
    country_code: Optional[str] = None,
    institution_tier: Optional[str] = None,
    research_tags: Optional[list[str]] = None,
    verification_status: Optional[str] = None,
    manual_notes: Optional[str] = None,
) -> dict:
    """
    Manually update fields on a professor profile in the local profiles database.

    Use this to write WebSearch-confirmed homepage URLs, verified positions,
    PI status, research tags, or manual notes. Only fields you provide are updated;
    omitted fields are left unchanged.

    Args:
        openalex_id: The professor's OpenAlex ID (required)
        homepage_url: Confirmed homepage URL
        position: Confirmed position title, e.g. "Assistant Professor"
        is_pi: Whether the professor is a PI
        pi_verification_source: Source of PI verification, e.g. "faculty_page"
        homepage_verification_source: Source of homepage verification
        institution: Confirmed current institution name
        country_code: Country code, e.g. "US"
        institution_tier: Tier, e.g. "R1"
        research_tags: List of research topic tags
        verification_status: "verified" | "needs_review" | "unverified"
        manual_notes: Free-text notes

    Returns:
        dict with "success" (bool) and "message".
    """
    return update_professor_profile_impl(openalex_id, {
        "homepage_url": homepage_url,
        "position": position,
        "is_pi": is_pi,
        "pi_verification_source": pi_verification_source,
        "homepage_verification_source": homepage_verification_source,
        "institution": institution,
        "country_code": country_code,
        "institution_tier": institution_tier,
        "research_tags": research_tags,
        "verification_status": verification_status,
        "manual_notes": manual_notes,
    })


@mcp.tool()
async def add_web_search_evidence(
    openalex_id: str,
    source_url: str,
    source_type: str,
    extracted: dict,
    source_title: Optional[str] = None,
    snippet: Optional[str] = None,
    confidence: str = "medium",
    auto_merge: bool = True,
) -> dict:
    """
    Add WebSearch evidence for a professor and optionally merge it into their profile.

    Call this after using web search to find a professor's faculty page or personal
    homepage. The extracted fields will be stored as evidence and (if auto_merge=True)
    merged into the professor's profile with cross-source verification.

    Args:
        openalex_id: The professor's OpenAlex ID
        source_url: URL of the evidence page
        source_type: One of: faculty_page, personal_homepage, lab_page,
                     scholar_page, paper_page, news, other
        extracted: Dict of extracted fields. Supported keys:
                   homepage_url, name, institution, country_code, position,
                   is_pi, research_tags (list), recent_papers (list of dicts)
        source_title: Title of the evidence page
        snippet: Relevant text snippet from the page
        confidence: "high" | "medium" | "low" (default "medium")
        auto_merge: If True (default), automatically merge evidence into profile

    Returns:
        dict with "evidence_id", "merged" (bool), and optionally "verification_status".
    """
    return add_web_search_evidence_impl(
        openalex_id=openalex_id, source_url=source_url, source_type=source_type,
        extracted=extracted, source_title=source_title, snippet=snippet,
        confidence=confidence, auto_merge=auto_merge,
    )


@mcp.tool()
async def profiles_inspect(
    name: Optional[str] = None,
    institution: Optional[str] = None,
    tag: Optional[str] = None,
    verification_status: Optional[str] = None,
    openalex_id: Optional[str] = None,
) -> dict:
    """
    Inspect the local professor profiles database.

    With no arguments, returns database statistics (counts by tier, country,
    verification status). With filters, returns matching professor summaries.
    With openalex_id, returns the full profile and its evidence.

    Args:
        name: Partial name match (case-insensitive)
        institution: Partial institution name match
        tag: Research tag to search for
        verification_status: Filter by "verified" | "needs_review" | "unverified"
        openalex_id: Get full profile + evidence for a specific professor

    Returns:
        dict with "stats" and/or "profiles" and/or "profile" + "evidence".
    """
    return profiles_inspect_impl(
        name=name, institution=institution, tag=tag,
        verification_status=verification_status, openalex_id=openalex_id,
    )


@mcp.tool()
async def profiles_export(
    format: str = "json",
    output_path: Optional[str] = None,
    include_evidence: bool = False,
) -> dict:
    """
    Export professor profiles from the local database.

    Args:
        format: "json" (default) | "markdown" | "csv"
        output_path: File path to save the export. If omitted, content is returned inline.
        include_evidence: If True, include web_search_evidence for each professor (JSON only)

    Returns:
        dict with "content" (string), "format", "total", and "saved_to" (path if saved).
    """
    return profiles_export_impl(
        format=format, output_path=output_path, include_evidence=include_evidence,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .search import search_professors_impl
from .details import get_professor_details_impl
from .ranking import rank_fit_impl, derive_domain_anchors
from .export import export_table_impl
from ..services.llm import QueryAnalyzer

_MAX_CONCURRENT_DETAILS = 3
_AUTO_MIN_RELEVANCE = 0.25  # relevance floor applied in auto-precision mode
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _auto_output_path(keywords: list[str]) -> str:
    """Generate a descriptive markdown filename from keywords + timestamp.

    Saved under PROFESSOR_FIT_OUTPUT_DIR if set, otherwise the project root.
    """
    slug_parts = []
    for kw in keywords[:3]:
        s = re.sub(r"[^a-z0-9]+", "-", kw.lower()).strip("-")
        if s:
            slug_parts.append(s)
    slug = "-".join(slug_parts)[:50] or "results"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = os.getenv("PROFESSOR_FIT_OUTPUT_DIR", str(_PROJECT_ROOT))
    filename = f"professor_fit_{slug}_{ts}.md"
    return str(Path(out_dir) / filename)


async def find_professors_impl(
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
    End-to-end professor finder: search -> details -> rank -> markdown export.

    Supports two modes:
      - Structured (recommended): client provides topic_keywords + domain_keywords.
        Topic queries receive topic_weight (default 3x) scoring boost over domain.
      - Legacy: only keywords provided. If LLM_API_KEY is configured, the server
        auto-analyzes intent; otherwise uses rule-based heuristics.

    required_keywords / min_relevance tighten results by dropping off-domain
    false positives. The Markdown table is ALWAYS saved to a file.
    """
    # Step 0: Intent analysis (only if client didn't provide topic/domain split)
    effective_topic = topic_keywords
    effective_domain = domain_keywords
    effective_topic_weight = topic_weight
    effective_domain_weight = domain_weight

    if not effective_topic and not effective_domain and keywords:
        analyzer = QueryAnalyzer()
        intent = await analyzer.analyze(keywords)
        effective_topic = intent.topic_keywords
        effective_domain = intent.domain_keywords
        effective_topic_weight = intent.topic_weight
        effective_domain_weight = intent.domain_weight

    # 1. Coarse search
    search_result = await search_professors_impl(
        keywords=keywords,
        regions=regions,
        institution_tier=institution_tier,
        limit=limit,
        since_year=since_year,
        topic_keywords=effective_topic,
        domain_keywords=effective_domain,
        topic_weight=effective_topic_weight,
        domain_weight=effective_domain_weight,
    )
    candidates = search_result.get("professors", [])

    # 2. Enrich with details (bounded concurrency, fault-tolerant)
    sem = asyncio.Semaphore(_MAX_CONCURRENT_DETAILS)

    async def _fetch_one(cand: dict):
        async with sem:
            # Pass search-resolved institution/region as hints so details does
            # not regress to OpenAlex's stale last_known_institutions.
            return await get_professor_details_impl(
                professor_id=cand["openalex_id"],
                hint_country=cand.get("country_code"),
                hint_institution=cand.get("institution"),
                hint_tier=cand.get("institution_tier"),
            )

    tasks = [_fetch_one(p) for p in candidates if p.get("openalex_id")]
    raw_details = await asyncio.gather(*tasks, return_exceptions=True)

    detailed: list[dict] = []
    for d in raw_details:
        if isinstance(d, dict) and "error" not in d:
            detailed.append(d)

    # 3. Rank (deterministic relevance + fit materials)
    # Precision: if the caller didn't specify domain anchors, auto-derive them
    # from the keywords (e.g. a blockchain search excludes off-domain people who
    # only match ambiguous terms like "consensus"/"byzantine"). Pass an explicit
    # list to override, or [] to disable the gate entirely.
    auto_anchored = required_keywords is None
    effective_required = (
        required_keywords if required_keywords is not None
        else derive_domain_anchors(keywords)
    )

    # In auto-precision mode, also apply a modest relevance floor so prolific
    # authors who merely touched the domain once (low relevance) are dropped,
    # while on-topic researchers (who match several query terms) are kept.
    effective_min_relevance = min_relevance
    if effective_min_relevance == 0.0 and auto_anchored and effective_required:
        effective_min_relevance = _AUTO_MIN_RELEVANCE

    rank_filters: dict = {}
    if effective_required:
        rank_filters["required_keywords"] = effective_required
    if effective_min_relevance:
        rank_filters["min_relevance"] = effective_min_relevance

    # Carry the topic/domain split (client-provided or auto-analyzed) into the
    # ranking stage so topic hits keep their weight advantage in the final score.
    user_interests: dict = {"keywords": keywords}
    if effective_topic or effective_domain:
        user_interests.update({
            "topic_keywords": effective_topic or [],
            "domain_keywords": effective_domain or [],
            "topic_weight": effective_topic_weight,
            "domain_weight": effective_domain_weight,
        })

    ranked = await rank_fit_impl(
        user_interests=user_interests,
        professors=detailed,
        filters=rank_filters or None,
    )

    # 4. Export markdown (default format). Auto-save to a generated file when the
    #    caller didn't specify a path, so every search produces a Markdown document.
    if output_path is None:
        output_path = _auto_output_path(keywords)
    export = export_table_impl(
        professors=ranked["ranked_professors"],
        format="markdown",
        include_summary=True,
        output_path=output_path,
    )
    saved_to = export.get("saved_to")
    if saved_to:
        saved_to = str(Path(saved_to).resolve())

    # Professors whose homepage couldn't be found from DBLP/OpenAlex. The client
    # (e.g. Cursor) should resolve these via its own web search using the query.
    homepage_todo = [
        {
            "name": entry["professor"].get("name"),
            "openalex_id": entry["professor"].get("openalex_id"),
            "search_query": entry["professor"].get("homepage_search_query"),
        }
        for entry in ranked["ranked_professors"]
        if not entry["professor"].get("homepage_url")
        and entry["professor"].get("homepage_search_query")
    ]

    result = {
        "ranked_professors": ranked["ranked_professors"],
        "total": ranked["total"],
        "keywords_used": ranked.get("keywords_used", keywords),
        "markdown": export["content"],
        "saved_to": saved_to,
        "homepage_resolution": {
            "needed": homepage_todo,
            "instruction": (
                "These professors have no homepage from DBLP/OpenAlex. Use your "
                "web search on each 'search_query' to find the professor's personal "
                "or faculty homepage, then update the table. Most professors have a "
                "personal homepage even when DBLP doesn't list one."
            ),
        } if homepage_todo else None,
    }
    return result

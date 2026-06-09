"""Live integration test — calls real APIs. Not part of unit test suite."""
import asyncio
from professor_fit_mcp.services.openalex import OpenAlexService
from professor_fit_mcp.services.dblp import DBLPService
from professor_fit_mcp.tools.search import search_professors_impl
from professor_fit_mcp.tools.details import get_professor_details_impl
from professor_fit_mcp.tools.ranking import rank_fit_impl
from professor_fit_mcp.tools.export import export_table_impl


async def main():
    print("=" * 60)
    print("1. search_professors")
    print("=" * 60)
    result = await search_professors_impl(
        keywords=["machine learning", "deep learning"],
        regions=["US"],
        limit=3,
    )
    print(f"  Found: {result['total_found']} professors")
    for p in result["professors"]:
        print(f"  - {p['name']} @ {p['institution']} | tier={p['institution_tier']} | h={p['h_index']}")

    if not result["professors"]:
        print("  No professors found, stopping.")
        return

    print()
    print("=" * 60)
    print("2. get_professor_details (first result)")
    print("=" * 60)
    first = result["professors"][0]
    details = await get_professor_details_impl(professor_id=first["openalex_id"])
    print(f"  Name: {details['name']}")
    print(f"  Institution: {details.get('institution', {}).get('value', 'N/A')}")
    print(f"  h-index: {details.get('h_index', {}).get('value', 'N/A')}")
    print(f"  Seniority: {details.get('seniority', 'N/A')}")
    print(f"  Homepage: {details.get('homepage_url', 'N/A')}")
    print(f"  Position: {details.get('position', {}).get('value', 'N/A')}")
    print(f"  Email: {details.get('email', 'N/A')}")
    n_papers = len(details.get("recent_papers", []))
    print(f"  Recent papers: {n_papers}")
    if n_papers > 0:
        for p in details["recent_papers"][:3]:
            print(f"    - [{p['year']}] {p['title'][:80]}")

    print()
    print("=" * 60)
    print("3. rank_fit (using detailed professors)")
    print("=" * 60)
    ranked = await rank_fit_impl(
        user_interests={"keywords": ["machine learning", "deep learning"]},
        professors=[details],
    )
    print(f"  Ranked: {ranked['total']} professors")
    for r in ranked["ranked_professors"]:
        print(f"  - {r['professor']['name']} | relevance={r['relevance_signal']}")

    print()
    print("=" * 60)
    print("4. export_table")
    print("=" * 60)
    export = export_table_impl(
        professors=ranked["ranked_professors"],
        format="markdown",
        include_summary=True,
    )
    print(export["content"])

    print()
    print("LIVE TEST COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())

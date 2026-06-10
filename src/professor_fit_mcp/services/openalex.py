from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Optional

import httpx

from ..models.paper import Paper

_BASE = "https://api.openalex.org"
_DEFAULT_EMAIL = os.getenv("OPENALEX_EMAIL", "")
_TIMEOUT = 15.0
_AUTHOR_FETCH_CONCURRENCY = 6  # bounded concurrency for author detail fetches


def _current_year() -> int:
    return datetime.now().year


def _extract_id(openalex_url: str) -> str:
    return openalex_url.rstrip("/").split("/")[-1]


def _parse_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    if not inverted_index:
        return None
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    if not words:
        return None
    return " ".join(words[i] for i in sorted(words))


class OpenAlexService:
    def __init__(self, email: str = _DEFAULT_EMAIL):
        self._email = email

    def _params(self, extra: Optional[dict] = None) -> dict:
        p: dict = {}
        if self._email:
            p["mailto"] = self._email
        if extra:
            p.update(extra)
        return p

    async def search_authors(
        self, name: str, institution: Optional[str] = None, limit: int = 20
    ) -> list[dict]:
        params = self._params({"search": name, "per_page": str(min(limit, 50))})
        if institution:
            params["filter"] = (
                f"last_known_institutions.display_name.search:{institution}"
            )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE}/authors", params=params)
            resp.raise_for_status()
        return [self._parse_author(a) for a in resp.json().get("results", [])]

    async def get_author(self, openalex_id: str) -> Optional[dict]:
        """Fetch a single author. Returns None on 404 or any network error."""
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE}/authors/{openalex_id}", params=self._params()
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
            return self._parse_author(resp.json())
        except Exception:
            return None

    # Domain synonym expansion: researchers describe the same area with different
    # vocabulary. Adding a few synonym queries improves recall for people whose
    # papers use adjacent terms (e.g. a BFT/consensus systems professor who never
    # writes the literal phrase "order fairness"). Extra queries still pass through
    # relevance ranking + the optional required_keywords anchor downstream.
    _DOMAIN_SYNONYMS = {
        "order fairness": [
            "order-fairness consensus",
            "fair transaction ordering",
            "fair ordering financial transactions",
            "ordering linearizability",
        ],
        "fair ordering": [
            "order-fairness byzantine consensus",
            "optimal fair ordering",
            "fair separability consensus",
        ],
        "transaction ordering": [
            "byzantine fault tolerant ordering",
            "atomic broadcast consensus",
            "transaction order manipulation",
        ],
        "mev": [
            "maximal extractable value",
            "frontrunning decentralized finance",
            "protected order flow",
        ],
        "blockchain": [
            "byzantine fault tolerance consensus",
            "distributed ledger consensus",
            "asynchronous BFT blockchain",
        ],
        "consensus": [
            "byzantine fault tolerance protocol",
            "atomic broadcast",
            "asynchronous byzantine agreement",
            "BFT consensus protocol",
        ],
        "blockchain consensus": [
            "asynchronous BFT consensus",
            "DAG consensus blockchain",
            "fair ordering protocol",
        ],
    }
    _MAX_QUERIES = 8

    @classmethod
    def _build_queries(cls, keywords: list[str]) -> list[str]:
        """
        Build search queries that widen recall WITHOUT sacrificing precision.

        Strategy:
          - The full combined query (most precise for the exact niche).
          - Each multi-word keyword as its own query (e.g. "order fairness").
          - A few domain-synonym queries (e.g. "byzantine fault tolerance consensus")
            so researchers using adjacent vocabulary are still surfaced.

        We deliberately do NOT issue broad single-word queries (e.g. "blockchain"
        alone), which would flood results with generalists.
        """
        cleaned = [k.strip() for k in keywords if k and k.strip()]
        if not cleaned:
            return []

        queries: list[str] = [" ".join(cleaned)]
        for kw in cleaned:
            if len(kw.split()) >= 2:  # specific multi-word phrase only
                queries.append(kw)

        # Synonym expansion (deduplicated, order-preserving)
        for kw in cleaned:
            for syn in cls._DOMAIN_SYNONYMS.get(kw.lower(), []):
                queries.append(syn)

        seen: set[str] = set()
        out: list[str] = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                out.append(q)
        return out[: cls._MAX_QUERIES]

    async def _fetch_works(
        self,
        query: str,
        since_year: int,
        per_page: int = 100,
        page: int = 1,
        country_codes: Optional[set[str]] = None,
    ) -> list[dict]:
        """Fetch one page of works for a query, sorted by relevance. Returns [] on any error."""
        filters = [f"from_publication_date:{since_year}-01-01"]
        if country_codes:
            # Push region filter down to the works query so the candidate author
            # pool is already in-region (huge recall win when filtering by region).
            codes = "|".join(sorted(country_codes))
            filters.append(f"authorships.institutions.country_code:{codes}")
        params = self._params({
            "search": query,
            "filter": ",".join(filters),
            "sort": "relevance_score:desc",
            "per_page": str(per_page),
            "page": str(page),
            "select": "id,relevance_score,authorships",
        })
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{_BASE}/works", params=params)
                resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception:
            return []

    @classmethod
    def _build_typed_queries(
        cls,
        topic_keywords: list[str],
        domain_keywords: list[str],
    ) -> list[tuple[str, str]]:
        """
        Build queries tagged with their type: "combined", "topic", or "domain".

        Priority order:
          1. Combined (topic + domain) — most precise for the exact niche
          2. Topic phrases and synonyms — find core researchers
          3. Domain phrases — widen recall with lower weight
        """
        combined = topic_keywords + domain_keywords
        results: list[tuple[str, str]] = []

        # Combined query (highest precision)
        if combined:
            results.append((" ".join(combined), "combined"))

        # Topic queries (high weight)
        for kw in topic_keywords:
            if len(kw.split()) >= 2:
                results.append((kw, "topic"))
        for kw in topic_keywords:
            for syn in cls._DOMAIN_SYNONYMS.get(kw.lower(), []):
                results.append((syn, "topic"))

        # Domain queries (lower weight) — only multi-word to avoid flooding
        for kw in domain_keywords:
            if len(kw.split()) >= 2:
                results.append((kw, "domain"))
        for kw in domain_keywords:
            for syn in cls._DOMAIN_SYNONYMS.get(kw.lower(), []):
                results.append((syn, "domain"))

        # Deduplicate preserving order
        seen: set[str] = set()
        out: list[tuple[str, str]] = []
        for q, qtype in results:
            if q not in seen:
                seen.add(q)
                out.append((q, qtype))
        return out[:cls._MAX_QUERIES]

    async def search_works_authors(
        self,
        keywords: list[str],
        since_year: int = 2021,
        limit: int = 20,
        country_codes: Optional[set[str]] = None,
        topic_keywords: Optional[list[str]] = None,
        domain_keywords: Optional[list[str]] = None,
        topic_weight: float = 3.0,
        domain_weight: float = 1.0,
    ) -> list[dict]:
        """
        Search works GLOBALLY, then extract and aggregate unique authors ranked
        by the RELEVANCE of the works they appear in.

        When topic_keywords / domain_keywords are provided, queries are split into
        groups with different scoring weights:
          - "combined" queries (topic+domain): weight = topic_weight * 1.5
          - "topic" queries: weight = topic_weight (default 3.0)
          - "domain" queries: weight = domain_weight (default 1.0)

        This ensures researchers whose papers directly address the TOPIC rank far
        above those who merely work in the broader DOMAIN.

        Falls back to the flat keyword behavior when topic/domain are not provided.
        """
        if isinstance(keywords, str):
            keywords = [keywords]

        # Build typed queries: either topic/domain split or legacy flat
        if topic_keywords or domain_keywords:
            typed_queries = self._build_typed_queries(
                topic_keywords or [], domain_keywords or [],
            )
        else:
            typed_queries = [(q, "combined") for q in self._build_queries(keywords)]

        max_pages = 5

        author_scores: dict[str, float] = {}
        author_paper_institutions: dict[str, set[tuple[str, str]]] = {}

        for query, query_type in typed_queries:
            # Determine score multiplier based on query type
            if query_type == "combined":
                query_weight = topic_weight * 1.5
            elif query_type == "topic":
                query_weight = topic_weight
            else:
                query_weight = domain_weight

            for page in range(1, max_pages + 1):
                works = await self._fetch_works(
                    query, since_year, per_page=100, page=page,
                )
                if not works:
                    break
                for work in works:
                    rel = work.get("relevance_score") or 1.0
                    authorships = work.get("authorships") or []
                    n = len(authorships)
                    for idx, authorship in enumerate(authorships):
                        author = authorship.get("author") or {}
                        author_id = author.get("id", "")
                        if not author_id:
                            continue
                        aid = _extract_id(author_id)
                        position_weight = 1.0
                        if n > 1 and (idx == 0 or idx == n - 1):
                            position_weight = 1.5
                        author_scores[aid] = (
                            author_scores.get(aid, 0.0)
                            + rel * position_weight * query_weight
                        )

                        for inst in (authorship.get("institutions") or []):
                            inst_name = inst.get("display_name") or ""
                            inst_country = inst.get("country_code") or ""
                            if inst_name and inst_country:
                                author_paper_institutions.setdefault(aid, set()).add(
                                    (inst_name, inst_country)
                                )

        sorted_ids = sorted(author_scores.items(), key=lambda x: x[1], reverse=True)

        if country_codes:
            candidate_cap = max(limit * 12, 200)
        else:
            candidate_cap = max(limit * 5, 80)
        candidate_ids = [aid for aid, _ in sorted_ids[:candidate_cap]]

        sem = asyncio.Semaphore(_AUTHOR_FETCH_CONCURRENCY)

        async def _resolve(aid: str) -> Optional[dict]:
            async with sem:
                return await self.get_author(aid)

        resolved = await asyncio.gather(*[_resolve(a) for a in candidate_ids])

        # Enrich with paper-level institution data
        for r in resolved:
            if r is None:
                continue
            aid = r.get("openalex_id", "")
            if aid in author_paper_institutions:
                r["_paper_institutions"] = list(author_paper_institutions[aid])

        valid = [r for r in resolved if r]

        # Full DBLP resolution for all candidates: provides accurate current
        # affiliation and homepage (DBLP is human-curated, more current than
        # OpenAlex for recent institutional moves).
        from .dblp import DBLPService
        dblp_svc = DBLPService()
        dblp_sem = asyncio.Semaphore(8)

        async def _resolve_dblp(author: dict) -> None:
            async with dblp_sem:
                name = author.get("name", "")
                if not name:
                    return
                try:
                    results = await dblp_svc.search_person(name, limit=1)
                    if results:
                        record = await dblp_svc.get_person_record(results[0]["pid"])
                        if record.get("affiliation"):
                            author["_dblp_affiliation"] = record["affiliation"]
                        if record.get("homepage_url"):
                            author["_dblp_homepage"] = record["homepage_url"]
                except Exception:
                    pass

        await asyncio.gather(*[_resolve_dblp(a) for a in valid])

        return valid

    async def get_recent_works(
        self, openalex_id: str, since_year: int = 2023, limit: int = 50
    ) -> list[Paper]:
        params = self._params(
            {
                "filter": f"authorships.author.id:{openalex_id},publication_year:{since_year}-{_current_year()}",
                "per_page": str(min(limit, 50)),
                "select": "id,title,publication_year,primary_location,abstract_inverted_index,authorships,doi,ids",
            }
        )
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{_BASE}/works", params=params)
                resp.raise_for_status()
            return [self._parse_work(w) for w in resp.json().get("results", [])]
        except Exception:
            return []

    def _parse_author(self, raw: dict) -> dict:
        openalex_url = raw.get("id", "")
        openalex_id = _extract_id(openalex_url) if openalex_url else ""
        institutions = raw.get("last_known_institutions") or []
        inst = institutions[0] if institutions else {}
        concepts = [
            c["display_name"]
            for c in (raw.get("x_concepts") or [])
            if c.get("score", 0) > 0.3
        ]
        counts_by_year = raw.get("counts_by_year") or []
        papers_last_3y = sum(
            c["works_count"] for c in counts_by_year if c["year"] >= 2023
        )
        stats = raw.get("summary_stats") or {}

        # Per-year affiliations are far more reliable than last_known_institutions,
        # which is often stale (e.g. shows a PhD-era institution after a move).
        affiliations = []
        for aff in (raw.get("affiliations") or []):
            ainst = aff.get("institution") or {}
            years = aff.get("years") or []
            affiliations.append({
                "institution": ainst.get("display_name"),
                "country_code": ainst.get("country_code"),
                "type": ainst.get("type"),
                "max_year": max(years) if years else None,
            })

        return {
            "openalex_id": openalex_id,
            "name": raw.get("display_name", ""),
            "institution": inst.get("display_name"),
            "country_code": inst.get("country_code"),
            "institution_type": inst.get("type"),
            "affiliations": affiliations,
            "h_index": stats.get("h_index"),
            "citation_count": raw.get("cited_by_count"),
            "works_count": raw.get("works_count"),
            "papers_last_3_years": papers_last_3y if papers_last_3y else None,
            "concepts": concepts,
            "homepage_url": raw.get("homepage_url"),
        }

    def _parse_work(self, raw: dict) -> Paper:
        location = raw.get("primary_location") or {}
        source = location.get("source") or {}
        venue = source.get("display_name")
        ids = raw.get("ids") or {}
        arxiv_url = ids.get("arxiv") or ""
        arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else None
        authors = [
            a["author"]["display_name"]
            for a in (raw.get("authorships") or [])
            if a.get("author", {}).get("display_name")
        ]
        return Paper(
            title=raw.get("title") or "",
            authors=authors,
            year=raw.get("publication_year"),
            venue=venue,
            abstract=_parse_abstract(raw.get("abstract_inverted_index")),
            doi=raw.get("doi"),
            arxiv_id=arxiv_id,
            url=arxiv_url or raw.get("doi"),
            source="openalex",
        )

from __future__ import annotations

import os
from typing import Optional

import httpx

from ..models.paper import Paper

_BASE = "https://api.openalex.org"
_DEFAULT_EMAIL = os.getenv("OPENALEX_EMAIL", "")
_TIMEOUT = 15.0


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
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_BASE}/authors/{openalex_id}", params=self._params()
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        return self._parse_author(resp.json())

    async def get_recent_works(
        self, openalex_id: str, since_year: int = 2023, limit: int = 50
    ) -> list[Paper]:
        params = self._params(
            {
                "filter": f"authorships.author.id:{openalex_id},publication_year:>={since_year}",
                "per_page": str(min(limit, 50)),
                "select": "id,title,publication_year,primary_location,abstract_inverted_index,authorships,doi,ids",
            }
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE}/works", params=params)
            resp.raise_for_status()
        return [self._parse_work(w) for w in resp.json().get("results", [])]

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
        return {
            "openalex_id": openalex_id,
            "name": raw.get("display_name", ""),
            "institution": inst.get("display_name"),
            "country_code": inst.get("country_code"),
            "institution_type": inst.get("type"),
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

from typing import Optional

import httpx
from bs4 import BeautifulSoup

_TIMEOUT = 10.0


class DBLPService:
    """DBLP person search — finds homepage URL and first publication year."""

    async def search_person(self, name: str, limit: int = 5) -> list[dict]:
        params = {"q": name, "format": "json", "h": str(limit)}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://dblp.org/search/author/api", params=params
            )
            resp.raise_for_status()
        hits = resp.json().get("result", {}).get("hits", {}).get("hit", [])
        if isinstance(hits, dict):
            hits = [hits]
        results = []
        for hit in hits:
            info = hit.get("info", {})
            dblp_url = info.get("url", "")
            pid = (
                "/".join(dblp_url.split("/pid/")[-1].split("/")[:2])
                if "/pid/" in dblp_url
                else ""
            )
            results.append(
                {"pid": pid, "name": info.get("author", ""), "dblp_url": dblp_url}
            )
        return results

    async def get_person_record(self, pid: str) -> dict:
        url = f"https://dblp.org/pid/{pid}.xml"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml-xml")
        note = soup.find("note", {"type": "source:homepage"})
        homepage_url = note.get_text(strip=True) if note else None
        years = [
            int(y.get_text(strip=True))
            for y in soup.find_all("year")
            if y.get_text(strip=True).isdigit()
        ]
        first_pub_year = min(years) if years else None
        return {
            "pid": pid,
            "homepage_url": homepage_url,
            "first_pub_year": first_pub_year,
        }

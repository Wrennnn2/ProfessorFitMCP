from typing import Optional

import httpx
from bs4 import BeautifulSoup

_TIMEOUT = 10.0

# URL hosts that are aggregator/profile sites, not a personal homepage.
_AGGREGATOR_HOSTS = (
    "scholar.google",
    "orcid.org",
    "dl.acm.org",
    "dblp.org",
    "semanticscholar.org",
    "researchgate.net",
    "linkedin.com",
    "wikidata.org",
    "wikipedia.org",
    "github.com",
    "twitter.com",
    "x.com",
    "mathgenealogy",
    "zbmath",
    "scopus.com",
    "researcherid",
    "ieee.org",
    "isni.org",
    "viaf.org",
)


def _is_homepage_url(url: str) -> bool:
    u = url.lower()
    return not any(host in u for host in _AGGREGATOR_HOSTS)


class DBLPService:
    """DBLP person search — finds homepage URL, current affiliation, first publication year."""

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

        person = soup.find("person")

        # Homepage: DBLP stores external links as <url> children of <person>.
        # The first non-aggregator link is the personal/faculty homepage.
        homepage_url = None
        if person:
            for url_tag in person.find_all("url"):
                link = url_tag.get_text(strip=True)
                if link and _is_homepage_url(link):
                    homepage_url = link
                    break

        # Current affiliation: <note type="affiliation"> without label="former".
        # DBLP curates these and they are far more accurate than OpenAlex's
        # last_known_institutions.
        affiliation = None
        former_affiliations: list[str] = []
        scope = person if person else soup
        for note in scope.find_all("note", {"type": "affiliation"}):
            text = note.get_text(strip=True)
            if not text:
                continue
            if note.get("label") == "former":
                former_affiliations.append(text)
            elif affiliation is None:
                affiliation = text

        years = [
            int(y.get_text(strip=True))
            for y in soup.find_all("year")
            if y.get_text(strip=True).isdigit()
        ]
        first_pub_year = min(years) if years else None

        return {
            "pid": pid,
            "homepage_url": homepage_url,
            "dblp_profile_url": f"https://dblp.org/pid/{pid}.html",
            "affiliation": affiliation,
            "former_affiliations": former_affiliations,
            "first_pub_year": first_pub_year,
        }

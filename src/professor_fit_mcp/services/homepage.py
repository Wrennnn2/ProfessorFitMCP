import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

_TIMEOUT = 10.0

_POSITION_PATTERNS = [
    r"(full\s+professor)",
    r"(associate\s+professor)",
    r"(assistant\s+professor)",
    r"(professor\s+of\s+\w+)",
    r"(research\s+scientist)",
    r"(principal\s+investigator)",
]
_POSITION_RE = re.compile("|".join(_POSITION_PATTERNS), re.IGNORECASE)

_ACCEPTING_KEYWORDS = [
    "looking for",
    "seeking",
    "recruiting",
    "accepting applications",
    "open positions",
    "phd openings",
    "graduate students",
    "开放招生",
    "招收",
]


class HomepageService:
    async def fetch(self, url: str) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "ProfessorFitMCP/0.1 (academic research tool)"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            return self._empty(error=str(exc))

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        return {
            "position": self._extract_position(text),
            "email": self._extract_email(soup),
            "lab_name": self._extract_lab_name(soup),
            "lab_url": self._extract_lab_url(soup),
            "accepting_signal": self._extract_accepting_signal(text),
            "error": None,
        }

    def _extract_position(self, text: str) -> Optional[str]:
        m = _POSITION_RE.search(text)
        return m.group(0).strip() if m else None

    def _extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        link = soup.find("a", href=re.compile(r"^mailto:", re.I))
        if link:
            return link["href"].replace("mailto:", "").strip().split("?")[0]
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", soup.get_text())
        return m.group(0) if m else None

    def _extract_lab_name(self, soup: BeautifulSoup) -> Optional[str]:
        lab_link = soup.find("a", string=re.compile(r"lab|group|center|institute", re.I))
        return lab_link.get_text(strip=True) if lab_link else None

    def _extract_lab_url(self, soup: BeautifulSoup) -> Optional[str]:
        lab_link = soup.find("a", href=re.compile(r"lab|group|center|institute", re.I))
        if lab_link:
            href = lab_link.get("href", "")
            if href.startswith("http"):
                return href
        return None

    def _extract_accepting_signal(self, text: str) -> Optional[dict]:
        lower = text.lower()
        for kw in _ACCEPTING_KEYWORDS:
            idx = lower.find(kw)
            if idx != -1:
                start = max(0, idx - 20)
                end = min(len(text), idx + len(kw) + 130)
                snippet = text[start:end].strip()
                return {"signal": "possibly_open", "snippet": snippet, "confidence": "low"}
        return None

    def _empty(self, error: str) -> dict:
        return {
            "position": None,
            "email": None,
            "lab_name": None,
            "lab_url": None,
            "accepting_signal": None,
            "error": error,
        }

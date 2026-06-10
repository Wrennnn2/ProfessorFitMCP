"""
LLM-powered query intent analysis.

Used as a FALLBACK when the MCP client (e.g. Cursor's Claude) does NOT
provide structured topic_keywords / domain_keywords. When the client DOES
provide them, this module is skipped entirely (zero cost).

Architecture:
  - Primary path: Client LLM (Cursor Claude) reads tool docstring, decomposes
    the query into topic/domain, and passes structured params → no server LLM needed.
  - Fallback path: If only flat `keywords` are provided, this analyzer runs:
    1. If LLM_API_KEY is set → call the configured LLM for intelligent decomposition.
    2. Otherwise → use rule-based heuristics.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_LLM_TIMEOUT = 15.0


def _llm_settings() -> dict:
    """Read LLM config from the environment at call time (not import time),
    so runtime configuration changes and test monkeypatching take effect."""
    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }

_SYSTEM_PROMPT = """\
You are an academic search intent analyzer. Given a list of research keywords \
provided by a user looking for professors, decompose them into two categories:

1. **topic_keywords**: The specific research problem or contribution the user \
cares about. The professor MUST have direct work on this. Include 2-4 synonym \
phrasings that academics commonly use for the same concept.

2. **domain_keywords**: The broader field or area where the research lives. \
Used as context/filter, not as the primary matching criterion.

Also output:
- topic_weight (float, default 3.0): how much more important topic matches are
- domain_weight (float, default 1.0): weight for domain-only matches
- corrections: list of {original, corrected} for any spelling errors detected

Respond ONLY with valid JSON matching this schema:
{
  "topic_keywords": ["..."],
  "domain_keywords": ["..."],
  "topic_weight": 3.0,
  "domain_weight": 1.0,
  "corrections": []
}
"""


@dataclass
class QueryIntent:
    topic_keywords: list[str]
    domain_keywords: list[str]
    topic_weight: float = 3.0
    domain_weight: float = 1.0
    corrections: list[dict] = field(default_factory=list)
    source: str = "rule"  # "llm" | "rule" | "client"


class QueryAnalyzer:
    """Analyze search keywords to separate topic (primary) from domain (context)."""

    async def analyze(self, keywords: list[str]) -> QueryIntent:
        """
        Attempt LLM analysis if configured, otherwise fall back to rules.
        """
        settings = _llm_settings()
        if settings["api_key"]:
            try:
                return await self._llm_analyze(keywords, settings)
            except Exception:
                logger.warning(
                    "LLM intent analysis failed; falling back to rule-based heuristics",
                    exc_info=True,
                )
        return self._rule_analyze(keywords)

    async def _llm_analyze(self, keywords: list[str], settings: dict) -> QueryIntent:
        """Call configured LLM API (OpenAI-compatible) for intent decomposition."""
        import httpx

        headers = {
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings["model"],
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Keywords: {json.dumps(keywords)}"},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{settings['base_url']}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()

        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)

        return QueryIntent(
            topic_keywords=data.get("topic_keywords", keywords[:1]),
            domain_keywords=data.get("domain_keywords", keywords[1:]),
            topic_weight=float(data.get("topic_weight", 3.0)),
            domain_weight=float(data.get("domain_weight", 1.0)),
            corrections=data.get("corrections", []),
            source="llm",
        )

    def _rule_analyze(self, keywords: list[str]) -> QueryIntent:
        """
        Heuristic decomposition when no LLM is available.

        Strategy:
          - Multi-word phrases (e.g. "order fairness") → likely topic
          - Single common domain words (e.g. "blockchain") → likely domain
          - If ambiguous, first keyword(s) = topic, rest = domain
        """
        if not keywords:
            return QueryIntent(topic_keywords=[], domain_keywords=[])

        _DOMAIN_SINGLES = {
            "blockchain", "defi", "ethereum", "bitcoin", "cryptocurrency",
            "smart contract", "web3", "ai", "ml", "nlp", "iot", "cloud",
            "security", "privacy", "networking", "database", "systems",
        }

        topic: list[str] = []
        domain: list[str] = []

        for kw in keywords:
            kw_lower = kw.lower().strip()
            if kw_lower in _DOMAIN_SINGLES:
                domain.append(kw)
            elif len(kw.split()) >= 2:
                topic.append(kw)
            else:
                domain.append(kw)

        # If no topic was identified, promote the first keyword
        if not topic and keywords:
            topic = [keywords[0]]
            domain = keywords[1:]

        # If no domain was identified, keep topic only (domain = empty)
        return QueryIntent(
            topic_keywords=topic,
            domain_keywords=domain,
            topic_weight=3.0,
            domain_weight=1.0,
            source="rule",
        )

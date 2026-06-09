from __future__ import annotations

import csv
import io

_FIELDNAMES = [
    "rank", "name", "institution", "country_code", "institution_tier",
    "h_index", "citation_count", "seniority", "relevance_signal", "homepage_url",
]


def _val(field):
    """Extract raw value from either a raw value or a SourcedField dict."""
    if isinstance(field, dict) and "value" in field:
        v = field["value"]
        return v if v is not None else ""
    return field if field is not None else ""


def to_csv(ranked: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_FIELDNAMES, extrasaction="ignore")
    writer.writeheader()
    for i, entry in enumerate(ranked, 1):
        prof = entry.get("professor", {})
        writer.writerow({
            "rank": i,
            "name": prof.get("name", ""),
            "institution": _val(prof.get("institution")),
            "country_code": prof.get("country_code", ""),
            "institution_tier": prof.get("institution_tier") or "",
            "h_index": _val(prof.get("h_index")),
            "citation_count": _val(prof.get("citation_count")),
            "seniority": prof.get("seniority") or "",
            "relevance_signal": entry.get("relevance_signal", ""),
            "homepage_url": prof.get("homepage_url") or "",
        })
    return output.getvalue()

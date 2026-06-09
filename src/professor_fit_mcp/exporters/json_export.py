from __future__ import annotations

import json


def to_json(ranked: list[dict]) -> str:
    output = []
    for i, entry in enumerate(ranked, 1):
        prof = entry.get("professor", {})
        output.append({
            "rank": i,
            "name": prof.get("name", ""),
            "institution": prof.get("institution", ""),
            "country_code": prof.get("country_code", ""),
            "institution_tier": prof.get("institution_tier"),
            "h_index": (prof.get("h_index") or {}).get("value"),
            "citation_count": (prof.get("citation_count") or {}).get("value"),
            "seniority": prof.get("seniority"),
            "relevance_signal": entry.get("relevance_signal"),
            "homepage_url": prof.get("homepage_url"),
            "concepts": prof.get("concepts", []),
            "accepting_students_signal": prof.get("accepting_students_signal"),
        })
    return json.dumps(output, ensure_ascii=False, indent=2)

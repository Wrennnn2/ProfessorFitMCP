import csv
import io
import json
import os

import pytest

from professor_fit_mcp.tools.export import export_table_impl

_RANKED = [
    {
        "professor": {
            "openalex_id": "A1",
            "name": "Alice Smith",
            "institution": "MIT",
            "country_code": "US",
            "institution_tier": "R1",
            "h_index": {"value": 65, "sources": ["openalex"], "confidence": "high"},
            "citation_count": {"value": 18000, "sources": ["openalex"], "confidence": "high"},
            "homepage_url": "https://alice.mit.edu",
            "seniority": "mid-career",
            "accepting_students_signal": None,
        },
        "relevance_signal": 0.9,
    }
]


def test_export_markdown_contains_name():
    result = export_table_impl(professors=_RANKED, format="markdown")
    assert "Alice Smith" in result["content"]
    assert "|" in result["content"]


def test_export_csv_parseable():
    result = export_table_impl(professors=_RANKED, format="csv")
    reader = csv.DictReader(io.StringIO(result["content"]))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice Smith"
    assert rows[0]["relevance_signal"] == "0.9"


def test_export_json_parseable():
    result = export_table_impl(professors=_RANKED, format="json")
    data = json.loads(result["content"])
    assert len(data) == 1
    assert data[0]["name"] == "Alice Smith"


def test_export_with_summary():
    result = export_table_impl(professors=_RANKED, format="markdown", include_summary=True)
    assert "1" in result["content"]


def test_export_to_file(tmp_path):
    out = str(tmp_path / "output.md")
    result = export_table_impl(professors=_RANKED, format="markdown", output_path=out)
    assert os.path.exists(out)
    assert result["saved_to"] == out


def test_export_unsupported_format():
    with pytest.raises(ValueError, match="Unsupported format"):
        export_table_impl(professors=_RANKED, format="xlsx")

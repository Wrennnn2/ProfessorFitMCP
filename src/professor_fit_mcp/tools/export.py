from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..exporters.markdown import to_markdown
from ..exporters.csv_export import to_csv
from ..exporters.json_export import to_json


def export_table_impl(
    professors: list[dict],
    format: str = "markdown",
    include_summary: bool = True,
    output_path: Optional[str] = None,
) -> dict:
    fmt = format.lower()
    if fmt == "markdown":
        content = to_markdown(professors, include_summary=include_summary)
    elif fmt == "csv":
        content = to_csv(professors)
    elif fmt == "json":
        content = to_json(professors)
    else:
        raise ValueError(f"Unsupported format: {format}. Use markdown, csv, or json.")

    result: dict = {"format": fmt, "content": content, "saved_to": None}
    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")
        result["saved_to"] = output_path
    return result

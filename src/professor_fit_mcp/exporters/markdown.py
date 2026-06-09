from __future__ import annotations


def _pipe_table(headers: list[str], rows: list[list]) -> str:
    col_widths = [len(h) for h in headers]
    str_rows = []
    for row in rows:
        cells = [str(c) for c in row]
        str_rows.append(cells)
        for i, c in enumerate(cells):
            col_widths[i] = max(col_widths[i], len(c))

    def _fmt_row(cells: list[str]) -> str:
        padded = [c.ljust(col_widths[i]) for i, c in enumerate(cells)]
        return "| " + " | ".join(padded) + " |"

    lines = [_fmt_row(headers)]
    lines.append("|" + "|".join("-" * (w + 2) for w in col_widths) + "|")
    for row in str_rows:
        lines.append(_fmt_row(row))
    return "\n".join(lines)


def _val(field) -> str:
    """Extract display value from either a raw value or a SourcedField dict."""
    if isinstance(field, dict) and "value" in field:
        v = field["value"]
        return str(v) if v is not None else "-"
    if field is None:
        return "-"
    return str(field)


def to_markdown(ranked: list[dict], include_summary: bool = False) -> str:
    rows = []
    for i, entry in enumerate(ranked, 1):
        prof = entry.get("professor", {})
        rows.append([
            i,
            prof.get("name", ""),
            _val(prof.get("institution")),
            prof.get("country_code", ""),
            prof.get("institution_tier") or "-",
            _val(prof.get("h_index")),
            _val(prof.get("citation_count")),
            prof.get("seniority") or "-",
            entry.get("relevance_signal", "-"),
            prof.get("homepage_url") or "-",
        ])
    headers = [
        "#", "Name", "Institution", "Country", "Tier",
        "h-index", "Citations", "Seniority", "Relevance", "Homepage",
    ]
    table = _pipe_table(headers, rows)
    summary = f"\n\n**Total:** {len(ranked)} professors" if include_summary else ""
    return f"# Professor Fit Results\n\n{table}{summary}\n"

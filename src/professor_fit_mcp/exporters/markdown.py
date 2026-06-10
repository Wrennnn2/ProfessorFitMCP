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


def _homepage_cell(prof: dict) -> str:
    """Render a clickable homepage link, or a search hint when no URL is known."""
    url = prof.get("homepage_url")
    if url:
        return f"[link]({url})"
    query = prof.get("homepage_search_query")
    if query:
        return f"_search:_ {query}"
    return "-"


def _top_papers_cell(entry: dict, prof: dict, max_papers: int = 2) -> str:
    """Show the titles of the top 1-2 representative recent papers."""
    papers = []
    materials = entry.get("fit_materials") or {}
    summary = materials.get("recent_papers_summary")
    if summary:
        papers = summary
    else:
        papers = prof.get("recent_papers") or []

    titles = []
    for p in papers[:max_papers]:
        title = p.get("title") if isinstance(p, dict) else getattr(p, "title", None)
        if title:
            # Escape pipe chars so they don't break the table
            titles.append(title.replace("|", "\\|"))
    return "; ".join(titles) if titles else "-"


def to_markdown(ranked: list[dict], include_summary: bool = True) -> str:
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
            _top_papers_cell(entry, prof),
            _homepage_cell(prof),
        ])
    headers = [
        "#", "Name", "Institution", "Country", "Tier",
        "h-index", "Citations", "Seniority", "Relevance", "Top Papers", "Homepage",
    ]
    table = _pipe_table(headers, rows)
    summary = f"\n\n**Total:** {len(ranked)} professors" if include_summary else ""
    return f"# Professor Fit Results\n\n{table}{summary}\n"

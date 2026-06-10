"""
Profile database tools: manual updates, web-search evidence, inspection, export.

Business logic for the profiles_* / update / evidence MCP tools lives here so
server.py stays a thin tool-registration layer (consistent with the other tools).
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Optional

from ..utils.profile_store import ProfileStore
from ..utils.profile_merger import ProfileMerger


def update_professor_profile_impl(openalex_id: str, updates: dict) -> dict:
    """Apply manual field updates to a stored professor profile."""
    updates = {k: v for k, v in updates.items() if v is not None}
    if not updates:
        return {"success": False, "message": "No fields provided to update."}

    store = ProfileStore()
    ok = store.update_profile_fields(openalex_id, updates)
    if ok:
        return {"success": True, "message": f"Updated {len(updates)} field(s) for {openalex_id}."}
    return {"success": False, "message": f"Profile {openalex_id} not found in local database."}


def add_web_search_evidence_impl(
    openalex_id: str,
    source_url: str,
    source_type: str,
    extracted: dict,
    source_title: Optional[str] = None,
    snippet: Optional[str] = None,
    confidence: str = "medium",
    auto_merge: bool = True,
) -> dict:
    """Store WebSearch evidence and optionally merge it into the profile."""
    store = ProfileStore()

    evidence = {
        "openalex_id": openalex_id,
        "professor_key": openalex_id,
        "source_url": source_url,
        "source_title": source_title,
        "source_type": source_type,
        "extracted_json": extracted,
        "snippet": snippet,
        "confidence": confidence,
    }
    row_id = store.add_evidence(evidence)
    result: dict = {"evidence_id": row_id, "merged": False}

    if auto_merge:
        profile = store.get_profile(openalex_id)
        if profile:
            all_evidence = store.get_evidence(openalex_id)
            merged = ProfileMerger.merge_evidence_into_profile(profile, all_evidence)
            tags_raw = merged.get("research_tags_json")
            tags = json.loads(tags_raw) if tags_raw else None
            merge_updates = {
                k: v for k, v in {
                    "homepage_url": merged.get("homepage_url"),
                    "position": merged.get("position"),
                    "is_pi": merged.get("is_pi"),
                    "pi_verification_source": merged.get("pi_verification_source"),
                    "homepage_verification_source": merged.get("homepage_verification_source"),
                    "institution": merged.get("institution"),
                    "country_code": merged.get("country_code"),
                    "verification_status": merged.get("verification_status"),
                    "research_tags": tags,
                }.items() if v is not None
            }
            store.update_profile_fields(openalex_id, merge_updates)
            result["merged"] = True
            result["verification_status"] = merged.get("verification_status")

    return result


def profiles_inspect_impl(
    name: Optional[str] = None,
    institution: Optional[str] = None,
    tag: Optional[str] = None,
    verification_status: Optional[str] = None,
    openalex_id: Optional[str] = None,
) -> dict:
    """Inspect the profiles database: stats, filtered summaries, or one full profile."""
    store = ProfileStore()
    result: dict = {}

    if openalex_id:
        profile = store.get_profile(openalex_id)
        evidence = store.get_evidence(openalex_id) if profile else []
        result["profile"] = profile
        result["evidence"] = evidence
        return result

    has_filter = any([name, institution, tag, verification_status])
    if has_filter:
        profiles = store.search_profiles(
            name=name, institution=institution,
            tag=tag, verification_status=verification_status,
        )
        result["profiles"] = profiles
        result["total"] = len(profiles)
    else:
        result["stats"] = store.stats()
        result["profiles"] = store.list_all()
        result["total"] = len(result["profiles"])

    return result


def _render_markdown(profiles: list[dict]) -> str:
    lines = ["# Professor Profiles Database\n"]
    lines.append(f"**Total:** {len(profiles)} professors\n")
    lines.append("| # | Name | Institution | Country | Tier | h-index | Status | Homepage |")
    lines.append("|---|------|-------------|---------|------|---------|--------|----------|")
    for i, p in enumerate(profiles, 1):
        hp = f"[link]({p['homepage_url']})" if p.get("homepage_url") else "-"
        lines.append(
            f"| {i} | {p.get('name','')} | {p.get('institution','')} "
            f"| {p.get('country_code','')} | {p.get('institution_tier','')} "
            f"| {p.get('h_index','')} | {p.get('verification_status','')} | {hp} |"
        )
    return "\n".join(lines)


def _render_csv(profiles: list[dict]) -> str:
    if not profiles:
        return ""
    fields = ["openalex_id", "name", "institution", "country_code",
              "institution_tier", "h_index", "citation_count",
              "position", "verification_status", "homepage_url"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(profiles)
    return buf.getvalue()


def profiles_export_impl(
    format: str = "json",
    output_path: Optional[str] = None,
    include_evidence: bool = False,
) -> dict:
    """Export all stored profiles as json/markdown/csv, optionally saved to a file."""
    store = ProfileStore()
    profiles = store.all_profiles()
    total = len(profiles)

    if format == "json":
        if include_evidence:
            for p in profiles:
                oid = p.get("openalex_id")
                if oid:
                    p["evidence"] = store.get_evidence(oid)
        content = json.dumps(profiles, ensure_ascii=False, indent=2)
    elif format == "markdown":
        content = _render_markdown(profiles)
    elif format == "csv":
        content = _render_csv(profiles)
    else:
        return {"error": f"Unsupported format: {format}. Use json, markdown, or csv."}

    result = {"content": content, "format": format, "total": total, "saved_to": None}
    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")
        result["saved_to"] = str(Path(output_path).resolve())

    return result

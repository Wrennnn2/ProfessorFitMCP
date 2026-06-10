from __future__ import annotations

import copy
import json


class ProfileMerger:
    """Merge multi-source data into a professor profile with conflict detection."""

    HOMEPAGE_PRIORITY = [
        "faculty_page", "personal_homepage", "dblp", "openalex", "scholar_page", "other",
    ]
    POSITION_PRIORITY = [
        "faculty_page", "personal_homepage", "homepage", "scholar_page", "openalex_heuristic",
    ]
    INSTITUTION_PRIORITY = [
        "faculty_page", "openalex_affiliations", "openalex", "dblp", "other",
    ]

    CONFLICT_FIELDS = ("institution", "position", "is_pi", "homepage_url", "country_code")

    @staticmethod
    def merge_evidence_into_profile(profile: dict, evidence_list: list[dict]) -> dict:
        merged = copy.deepcopy(profile)
        if not evidence_list:
            return merged

        conflicts = ProfileMerger._detect_conflicts(profile, evidence_list)
        merged["conflicts_json"] = json.dumps(conflicts, ensure_ascii=False) if conflicts else None

        best_homepage = ProfileMerger._pick_best(
            evidence_list, "homepage_url", ProfileMerger.HOMEPAGE_PRIORITY,
        )
        if best_homepage is not None:
            merged["homepage_url"] = best_homepage["value"]
            merged["homepage_source"] = best_homepage["source"]
            merged["homepage_verification_source"] = best_homepage["source"]

        best_position = ProfileMerger._pick_best(
            evidence_list, "position", ProfileMerger.POSITION_PRIORITY,
        )
        if best_position is not None:
            merged["position"] = best_position["value"]

        best_is_pi = ProfileMerger._pick_best(
            evidence_list, "is_pi", ProfileMerger.POSITION_PRIORITY,
        )
        if best_is_pi is not None:
            merged["is_pi"] = 1 if best_is_pi["value"] else 0
            merged["pi_verification_source"] = best_is_pi["source"]

        best_institution = ProfileMerger._pick_best(
            evidence_list, "institution", ProfileMerger.INSTITUTION_PRIORITY,
        )
        if best_institution is not None:
            merged["institution"] = best_institution["value"]

        best_country = ProfileMerger._pick_best(
            evidence_list, "country_code", ProfileMerger.INSTITUTION_PRIORITY,
        )
        if best_country is not None:
            merged["country_code"] = best_country["value"]

        existing_concepts = []
        if merged.get("concepts_json"):
            try:
                existing_concepts = json.loads(merged["concepts_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        evidence_tags: list[list] = []
        for ev in evidence_list:
            extracted = _parse_extracted(ev)
            tags = extracted.get("research_tags")
            if isinstance(tags, list):
                evidence_tags.append(tags)

        merged_tags = ProfileMerger._merge_research_tags(existing_concepts, evidence_tags)
        merged["research_tags_json"] = json.dumps(merged_tags, ensure_ascii=False) if merged_tags else None

        existing_papers = []
        if merged.get("recent_papers_json"):
            try:
                existing_papers = json.loads(merged["recent_papers_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        existing_titles = {
            (p.get("title") or "").lower().strip() for p in existing_papers if p.get("title")
        }
        for ev in evidence_list:
            extracted = _parse_extracted(ev)
            for paper in extracted.get("recent_papers", []):
                title = (paper.get("title") or "").lower().strip()
                if title and title not in existing_titles:
                    existing_papers.append(paper)
                    existing_titles.add(title)
        merged["recent_papers_json"] = json.dumps(existing_papers, ensure_ascii=False)

        merged["verification_status"] = ProfileMerger._determine_verification_status(
            merged, evidence_list, conflicts,
        )

        return merged

    @staticmethod
    def _detect_conflicts(profile: dict, evidence_list: list[dict]) -> dict:
        conflicts: dict[str, list[dict]] = {}

        for field in ProfileMerger.CONFLICT_FIELDS:
            values_seen: list[dict] = []

            profile_val = profile.get(field)
            if profile_val is not None:
                values_seen.append({
                    "value": profile_val,
                    "source": "profile",
                    "confidence": "medium",
                })

            for ev in evidence_list:
                extracted = _parse_extracted(ev)
                ev_val = extracted.get(field)
                if ev_val is None:
                    continue
                values_seen.append({
                    "value": ev_val,
                    "source": ev.get("source_type", "other"),
                    "confidence": ev.get("confidence", "medium"),
                })

            unique_vals = {_normalize_for_comparison(v["value"]) for v in values_seen}
            if len(unique_vals) > 1:
                conflicts[field] = values_seen

        return conflicts

    @staticmethod
    def _merge_research_tags(concepts: list, evidence_tags: list[list]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for tag in concepts:
            tag_str = str(tag).strip()
            lower = tag_str.lower()
            if lower and lower not in seen:
                seen.add(lower)
                result.append(tag_str)

        for tag_list in evidence_tags:
            for tag in tag_list:
                tag_str = str(tag).strip()
                lower = tag_str.lower()
                if lower and lower not in seen:
                    seen.add(lower)
                    result.append(tag_str)

        return sorted(result, key=str.lower)

    @staticmethod
    def _determine_verification_status(
        profile: dict, evidence_list: list[dict], conflicts: dict,
    ) -> str:
        for ev in evidence_list:
            if (
                ev.get("source_type") == "faculty_page"
                and ev.get("confidence") == "high"
            ):
                return "verified"

        high_sources: list[dict] = []
        for ev in evidence_list:
            if ev.get("confidence") == "high":
                high_sources.append(ev)
        if len(high_sources) >= 2:
            return "verified"

        if conflicts:
            return "needs_review"

        return "unverified"

    @staticmethod
    def _pick_best(
        evidence_list: list[dict],
        field: str,
        priority: list[str],
    ) -> dict | None:
        candidates: list[tuple[int, dict]] = []
        for ev in evidence_list:
            extracted = _parse_extracted(ev)
            val = extracted.get(field)
            if val is None:
                continue
            source_type = ev.get("source_type", "other")
            try:
                rank = priority.index(source_type)
            except ValueError:
                rank = len(priority)
            candidates.append((rank, {"value": val, "source": source_type}))
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]


def _parse_extracted(evidence: dict) -> dict:
    raw = evidence.get("extracted_json", {})
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return raw if isinstance(raw, dict) else {}


def _normalize_for_comparison(value) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).strip().lower()

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class ProfileStore:
    """SQLite-backed persistent store for professor profiles, evidence, and events."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.getenv(
                "PROFESSOR_PROFILES_DB_PATH",
                str(_PROJECT_ROOT / "professor_profiles.db"),
            )
        self._db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        """Connection that commits on success, rolls back on error, and always closes.

        ``with sqlite3.Connection`` alone only manages the transaction; it never
        closes the connection, which leaks handles and leaves WAL sidecar files.
        """
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS professor_profiles (
                    openalex_id TEXT PRIMARY KEY,
                    dblp_pid TEXT,
                    name TEXT NOT NULL,
                    institution TEXT,
                    country_code TEXT,
                    institution_tier TEXT,
                    position TEXT,
                    is_pi INTEGER,
                    pi_verification_source TEXT,
                    h_index INTEGER,
                    citation_count INTEGER,
                    works_count INTEGER,
                    papers_last_3_years INTEGER,
                    seniority TEXT,
                    homepage_url TEXT,
                    homepage_source TEXT,
                    homepage_verification_source TEXT,
                    email TEXT,
                    lab_name TEXT,
                    lab_url TEXT,
                    concepts_json TEXT,
                    research_tags_json TEXT,
                    recent_papers_json TEXT,
                    profile_json TEXT,
                    verification_status TEXT DEFAULT 'unverified',
                    conflicts_json TEXT,
                    manual_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    dynamic_refreshed_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS web_search_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    openalex_id TEXT,
                    professor_key TEXT NOT NULL,
                    source_url TEXT,
                    source_title TEXT,
                    source_type TEXT,
                    extracted_json TEXT NOT NULL,
                    snippet TEXT,
                    confidence TEXT DEFAULT 'medium',
                    fetched_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profile_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    openalex_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details_json TEXT,
                    timestamp TEXT NOT NULL
                )
            """)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _extract_value(field):
        """Extract the plain value from a sourced field dict or return as-is."""
        if isinstance(field, dict) and "value" in field:
            return field["value"]
        return field

    def upsert_profile(self, profile: dict) -> None:
        openalex_id = profile.get("openalex_id")
        if not openalex_id:
            return

        now = self._now()
        name = profile.get("name", "")

        institution = self._extract_value(profile.get("institution"))
        country_code = profile.get("country_code")
        institution_tier = profile.get("institution_tier")
        position = self._extract_value(profile.get("position"))

        is_pi_raw = self._extract_value(profile.get("is_pi"))
        is_pi: Optional[int] = None
        if is_pi_raw is True:
            is_pi = 1
        elif is_pi_raw is False:
            is_pi = 0

        pi_src = profile.get("is_pi")
        pi_verification_source = None
        if isinstance(pi_src, dict):
            sources = pi_src.get("sources", [])
            pi_verification_source = sources[0] if sources else None

        h_index = self._extract_value(profile.get("h_index"))
        citation_count = self._extract_value(profile.get("citation_count"))
        works_count = profile.get("works_count")
        papers_last_3_years = profile.get("papers_last_3_years")
        seniority = profile.get("seniority")
        homepage_url = profile.get("homepage_url")
        homepage_source = profile.get("homepage_source")
        email = profile.get("email")
        lab_name = profile.get("lab_name")
        lab_url = profile.get("lab_url")

        concepts = profile.get("concepts", [])
        concepts_json = json.dumps(concepts, ensure_ascii=False) if concepts else None
        recent_papers = profile.get("recent_papers", [])
        recent_papers_json = json.dumps(recent_papers, ensure_ascii=False) if recent_papers else None
        profile_json = json.dumps(profile, ensure_ascii=False)

        with self._db() as conn:
            existing = conn.execute(
                "SELECT * FROM professor_profiles WHERE openalex_id = ?",
                (openalex_id,),
            ).fetchone()

            if existing is None:
                conn.execute("""
                    INSERT INTO professor_profiles (
                        openalex_id, dblp_pid, name, institution, country_code,
                        institution_tier, position, is_pi, pi_verification_source,
                        h_index, citation_count, works_count, papers_last_3_years,
                        seniority, homepage_url, homepage_source,
                        homepage_verification_source, email, lab_name, lab_url,
                        concepts_json, research_tags_json, recent_papers_json,
                        profile_json, verification_status, conflicts_json,
                        manual_notes, created_at, updated_at, dynamic_refreshed_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, NULL, ?, ?, 'unverified', NULL, NULL, ?, ?, NULL
                    )
                """, (
                    openalex_id, profile.get("dblp_pid"), name, institution,
                    country_code, institution_tier, position, is_pi,
                    pi_verification_source, h_index, citation_count, works_count,
                    papers_last_3_years, seniority, homepage_url, homepage_source,
                    None, email, lab_name, lab_url,
                    concepts_json, recent_papers_json, profile_json,
                    now, now,
                ))
            else:
                # Existing row: refresh dynamic data but NEVER clobber
                # verification_status / research_tags_json / manual_notes /
                # conflicts_json / homepage_verification_source, and only touch
                # identity fields while the profile is still unverified.
                # Manually verified or needs_review profiles keep their
                # identity fields until resolved via update_profile_fields /
                # evidence merge.
                updates: dict = {
                    "dblp_pid": profile.get("dblp_pid") or existing["dblp_pid"],
                    "name": name or existing["name"],
                    "h_index": h_index,
                    "citation_count": citation_count,
                    "works_count": works_count,
                    "papers_last_3_years": papers_last_3_years,
                    "seniority": seniority or existing["seniority"],
                    "email": email or existing["email"],
                    "lab_name": lab_name or existing["lab_name"],
                    "lab_url": lab_url or existing["lab_url"],
                    "concepts_json": concepts_json or existing["concepts_json"],
                    "recent_papers_json": recent_papers_json or existing["recent_papers_json"],
                    "profile_json": profile_json,
                    "updated_at": now,
                }

                identity_unlocked = (
                    (existing["verification_status"] or "unverified") == "unverified"
                )
                if identity_unlocked:
                    identity_fields = {
                        "institution": institution,
                        "country_code": country_code,
                        "institution_tier": institution_tier,
                        "position": position,
                        "is_pi": is_pi,
                        "pi_verification_source": pi_verification_source,
                        "homepage_url": homepage_url,
                        "homepage_source": homepage_source,
                    }
                    for key, value in identity_fields.items():
                        if value is not None:
                            updates[key] = value

                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE professor_profiles SET {set_clause} WHERE openalex_id = ?",
                    [*updates.values(), openalex_id],
                )

        event_type = "updated" if existing else "created"
        self._log_event(openalex_id, event_type, {"source": "upsert_profile"})

    def get_profile(self, openalex_id: str) -> dict | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM professor_profiles WHERE openalex_id = ?",
                (openalex_id,),
            ).fetchone()
        return dict(row) if row else None

    def search_profiles(
        self,
        *,
        name: str | None = None,
        institution: str | None = None,
        tag: str | None = None,
        verification_status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        clauses: list[str] = []
        params: list = []

        if name:
            clauses.append("name LIKE ?")
            params.append(f"%{name}%")
        if institution:
            clauses.append("institution LIKE ?")
            params.append(f"%{institution}%")
        if tag:
            # Match the JSON-quoted tag (e.g. %"machine learning"%) so "ai"
            # does not substring-match inside "explainai".
            clauses.append("research_tags_json LIKE ?")
            params.append(f"%{json.dumps(tag, ensure_ascii=False)}%")
        if verification_status:
            clauses.append("verification_status = ?")
            params.append(verification_status)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        with self._db() as conn:
            rows = conn.execute(
                f"SELECT * FROM professor_profiles {where} LIMIT ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def list_all(self, limit: int = 100) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT openalex_id, name, institution, institution_tier, "
                "verification_status FROM professor_profiles LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with self._db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM professor_profiles").fetchone()[0]

            by_tier = {}
            for row in conn.execute(
                "SELECT institution_tier, COUNT(*) AS cnt FROM professor_profiles GROUP BY institution_tier"
            ).fetchall():
                by_tier[row["institution_tier"] or "unknown"] = row["cnt"]

            by_country = {}
            for row in conn.execute(
                "SELECT country_code, COUNT(*) AS cnt FROM professor_profiles GROUP BY country_code"
            ).fetchall():
                by_country[row["country_code"] or "unknown"] = row["cnt"]

            by_status = {}
            for row in conn.execute(
                "SELECT verification_status, COUNT(*) AS cnt FROM professor_profiles GROUP BY verification_status"
            ).fetchall():
                by_status[row["verification_status"] or "unverified"] = row["cnt"]

            total_evidence = conn.execute("SELECT COUNT(*) FROM web_search_evidence").fetchone()[0]
            total_events = conn.execute("SELECT COUNT(*) FROM profile_events").fetchone()[0]

        return {
            "total_profiles": total,
            "by_tier": by_tier,
            "by_country": by_country,
            "by_verification_status": by_status,
            "total_evidence": total_evidence,
            "total_events": total_events,
        }

    def add_evidence(self, evidence: dict) -> int:
        now = self._now()
        with self._db() as conn:
            cursor = conn.execute("""
                INSERT INTO web_search_evidence (
                    openalex_id, professor_key, source_url, source_title,
                    source_type, extracted_json, snippet, confidence, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evidence.get("openalex_id"),
                evidence["professor_key"],
                evidence.get("source_url"),
                evidence.get("source_title"),
                evidence.get("source_type"),
                json.dumps(evidence["extracted_json"], ensure_ascii=False)
                if isinstance(evidence["extracted_json"], dict)
                else evidence["extracted_json"],
                evidence.get("snippet"),
                evidence.get("confidence", "medium"),
                now,
            ))
            row_id = cursor.lastrowid

        openalex_id = evidence.get("openalex_id")
        if openalex_id:
            self._log_event(openalex_id, "web_evidence_added", {
                "evidence_id": row_id,
                "source_type": evidence.get("source_type"),
            })
        return row_id

    def get_evidence(self, openalex_id: str) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute(
                "SELECT * FROM web_search_evidence WHERE openalex_id = ? ORDER BY fetched_at DESC",
                (openalex_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_profile_fields(self, openalex_id: str, updates: dict) -> bool:
        allowed = {
            "homepage_url", "position", "is_pi", "pi_verification_source",
            "homepage_verification_source", "research_tags", "manual_notes",
            "verification_status", "institution", "country_code", "institution_tier",
        }
        now = self._now()
        set_clauses: list[str] = []
        params: list = []

        for key, value in updates.items():
            if key not in allowed:
                continue
            if key == "research_tags":
                set_clauses.append("research_tags_json = ?")
                params.append(json.dumps(value, ensure_ascii=False))
            elif key == "is_pi":
                set_clauses.append("is_pi = ?")
                params.append(1 if value else (0 if value is False else None))
            else:
                set_clauses.append(f"{key} = ?")
                params.append(value)

        if not set_clauses:
            return False

        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(openalex_id)

        with self._db() as conn:
            result = conn.execute(
                f"UPDATE professor_profiles SET {', '.join(set_clauses)} WHERE openalex_id = ?",
                params,
            )
            if result.rowcount == 0:
                return False

        self._log_event(openalex_id, "manual_update", {"fields": list(updates.keys())})
        return True

    def all_profiles(self) -> list[dict]:
        with self._db() as conn:
            rows = conn.execute("SELECT * FROM professor_profiles").fetchall()
        return [dict(r) for r in rows]

    def export_profiles(self, format: str = "json") -> str:
        """Export all profiles as a JSON string.

        Rendering to other formats (markdown/csv) lives in tools/profiles.py.
        """
        if format != "json":
            raise ValueError(
                f"ProfileStore.export_profiles only supports 'json', got {format!r}. "
                "Use tools.profiles.profiles_export_impl for markdown/csv."
            )
        return json.dumps(self.all_profiles(), ensure_ascii=False, indent=2)

    def _log_event(self, openalex_id: str, event_type: str, details: dict | None = None) -> None:
        now = self._now()
        details_json = json.dumps(details, ensure_ascii=False) if details else None
        with self._db() as conn:
            conn.execute(
                "INSERT INTO profile_events (openalex_id, event_type, details_json, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (openalex_id, event_type, details_json, now),
            )

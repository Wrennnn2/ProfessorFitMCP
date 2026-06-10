import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Cache:
    """SQLite-backed cache with TTL support."""

    PROFESSOR_TTL = 7 * 24 * 3600   # 7 days
    HOMEPAGE_TTL = 1 * 24 * 3600    # 1 day

    def __init__(self, db_path: "Path | str | None" = None):
        if db_path is None:
            db_path = os.getenv(
                "PROFESSOR_FIT_CACHE_PATH",
                str(_PROJECT_ROOT / "professor_fit_cache.db"),
            )
        self._db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    namespace TEXT NOT NULL,
                    key       TEXT NOT NULL,
                    value     TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    PRIMARY KEY (namespace, key)
                )
            """)

    def get(self, key: str, namespace: str) -> Optional[Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE namespace=? AND key=?",
                (namespace, key),
            ).fetchone()
        if row is None:
            return None
        value_json, expires_at = row
        if time.time() > expires_at:
            return None
        return json.loads(value_json)

    def set(self, key: str, value: Any, namespace: str, ttl_seconds: int) -> None:
        expires_at = time.time() + ttl_seconds
        value_json = json.dumps(value, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (namespace, key, value, expires_at) VALUES (?, ?, ?, ?)",
                (namespace, key, value_json, expires_at),
            )

import time
from pathlib import Path
from professor_fit_mcp.utils.cache import Cache


def test_cache_miss_returns_none(tmp_path):
    cache = Cache(tmp_path / "test.db")
    assert cache.get("missing_key", "test") is None


def test_cache_set_and_get(tmp_path):
    cache = Cache(tmp_path / "test.db")
    cache.set("k1", {"name": "Alice"}, "professors", ttl_seconds=3600)
    result = cache.get("k1", "professors")
    assert result == {"name": "Alice"}


def test_cache_expires(tmp_path):
    cache = Cache(tmp_path / "test.db")
    cache.set("k2", "value", "test", ttl_seconds=1)
    time.sleep(1.1)
    assert cache.get("k2", "test") is None


def test_cache_overwrite(tmp_path):
    cache = Cache(tmp_path / "test.db")
    cache.set("k3", "old", "test", ttl_seconds=3600)
    cache.set("k3", "new", "test", ttl_seconds=3600)
    assert cache.get("k3", "test") == "new"


def test_cache_different_namespaces(tmp_path):
    cache = Cache(tmp_path / "test.db")
    cache.set("k", "prof_data", "professors", ttl_seconds=3600)
    cache.set("k", "home_data", "homepage", ttl_seconds=3600)
    assert cache.get("k", "professors") == "prof_data"
    assert cache.get("k", "homepage") == "home_data"

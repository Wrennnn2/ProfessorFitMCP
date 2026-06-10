import json
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "institutions"


class InstitutionClassifier:
    def __init__(self, data_dir: Path = _DATA_DIR):
        self._index: dict[str, dict] = {}
        self._load(data_dir)

    def _load(self, data_dir: Path) -> None:
        configs = [
            ("us_r1.json", "R1", "US"),
            ("uk_russell.json", "Russell", "GB"),
            ("au_go8.json", "Go8", "AU"),
            ("ca_u15.json", "U15", "CA"),
            ("de_tu9.json", "TU9", "DE"),
            ("jp_imperial.json", "Imperial", "JP"),
            ("kr_sky.json", "SKY", "KR"),
            ("hk_top5.json", "HK5", "HK"),
        ]
        for filename, tier, country in configs:
            path = data_dir / filename
            if not path.exists():
                continue
            names: list[str] = json.loads(path.read_text(encoding="utf-8"))
            for name in names:
                self._index[name.lower()] = {"tier": tier, "country": country}

        cn_path = data_dir / "cn_985_211.json"
        if cn_path.exists():
            data = json.loads(cn_path.read_text(encoding="utf-8"))
            for tier, names in data.items():
                for name in names:
                    self._index[name.lower()] = {"tier": tier.upper(), "country": "CN"}

    def _country_ok(self, info: dict, country_code: Optional[str]) -> bool:
        """When a country is known, only accept index entries from that country.

        Prevents same-name collisions across countries, e.g. US "Northeastern
        University" vs the Chinese (211) "Northeastern University".
        """
        if not country_code:
            return True
        return info["country"] == country_code

    def classify(self, institution_name: str, country_code: Optional[str] = None) -> dict:
        key = institution_name.lower().strip()
        if not key:
            return {"tier": None, "country": country_code}

        # 1. Exact match (must agree on country if one is provided)
        entry = self._index.get(key)
        if entry and self._country_ok(entry, country_code):
            return {"tier": entry["tier"], "country": entry["country"]}

        # 2. Fuzzy match: a known institution name is contained in the query
        #    or vice versa (e.g. "Berkeley College" vs "University of California, Berkeley").
        #    Prefer the longest matching known name to avoid spurious short hits.
        best: Optional[dict] = None
        best_len = 0
        for known_name, info in self._index.items():
            if len(known_name) < 5:
                continue  # skip very short names to avoid false positives
            if not self._country_ok(info, country_code):
                continue
            if known_name in key or key in known_name:
                if len(known_name) > best_len:
                    best = info
                    best_len = len(known_name)
        if best:
            return {"tier": best["tier"], "country": best["country"]}

        return {"tier": None, "country": country_code}

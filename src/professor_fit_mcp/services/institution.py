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

    def classify(self, institution_name: str, country_code: Optional[str] = None) -> dict:
        key = institution_name.lower().strip()
        entry = self._index.get(key)
        if entry:
            return {"tier": entry["tier"], "country": entry["country"]}
        return {"tier": None, "country": country_code}

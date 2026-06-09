# Professor Fit MCP — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Python MCP server，帮 PhD 申请者匹配教授——输入研究兴趣关键词，输出带溯源与置信度的教授数据，供 client LLM 生成 fit 表格。

**Architecture:** 轻服务器——OpenAlex 作为主干（免费、无 key、自带消歧），DBLP 补充 CS 主页 URL 与首发年，直接对 homepage best-effort 抓取；server 只做数据聚合，语义 fit 判断由 client LLM 完成。4 个 MCP 工具：search_professors → get_professor_details → rank_fit → export_table。

**Tech Stack:** Python 3.10+, mcp[cli]>=1.6.0 (FastMCP), pydantic v2, httpx, beautifulsoup4, tabulate, pytest, pytest-asyncio

---

## 文件结构

```
src/professor_fit_mcp/
├── __init__.py
├── server.py                    # MCP server 入口，注册 4 个工具
├── models/
│   ├── __init__.py
│   ├── common.py                # SourcedField, Confidence type
│   ├── paper.py                 # Paper model
│   └── professor.py             # Professor model
├── services/
│   ├── __init__.py
│   ├── openalex.py              # OpenAlex API（作者搜索/详情/近期论文+摘要）
│   ├── dblp.py                  # DBLP person API（主页URL/首发年）
│   ├── homepage.py              # 主页抓取（职称/email/lab/招生信号）
│   └── institution.py           # 院校分级清单查询
├── tools/
│   ├── __init__.py
│   ├── search.py                # search_professors 实现
│   ├── details.py               # get_professor_details 实现
│   ├── ranking.py               # rank_fit 实现（整词匹配 + 打包材料）
│   └── export.py                # export_table 实现
├── exporters/
│   ├── __init__.py
│   ├── markdown.py
│   ├── csv_export.py
│   └── json_export.py
└── utils/
    ├── __init__.py
    ├── cache.py                 # SQLite 缓存（TTL：教授7天，主页1天）
    └── text_processing.py       # whole_word_match（整词匹配）
data/institutions/
├── us_r1.json
├── cn_985_211.json
├── uk_russell.json
├── au_go8.json
├── ca_u15.json
├── de_tu9.json
├── jp_imperial.json
└── kr_sky.json
tests/
├── conftest.py
├── test_models.py
├── test_cache.py
├── test_text_processing.py
├── test_institution.py
├── test_openalex.py
├── test_dblp.py
├── test_homepage.py
├── test_tools_search.py
├── test_tools_details.py
├── test_tools_ranking.py
└── test_tools_export.py
pyproject.toml
.gitignore
.env.example
README.md
```

---

## Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `src/professor_fit_mcp/__init__.py`（及所有子包 `__init__.py`）
- Create: `.gitignore`, `.env.example`

- [ ] **Step 1: 创建目录结构**

```powershell
New-Item -ItemType Directory -Force src/professor_fit_mcp/models
New-Item -ItemType Directory -Force src/professor_fit_mcp/services
New-Item -ItemType Directory -Force src/professor_fit_mcp/tools
New-Item -ItemType Directory -Force src/professor_fit_mcp/exporters
New-Item -ItemType Directory -Force src/professor_fit_mcp/utils
New-Item -ItemType Directory -Force data/institutions
New-Item -ItemType Directory -Force tests
```

- [ ] **Step 2: 创建所有 `__init__.py`（全部为空）**

```powershell
$pkgs = @(
  "src/professor_fit_mcp/__init__.py",
  "src/professor_fit_mcp/models/__init__.py",
  "src/professor_fit_mcp/services/__init__.py",
  "src/professor_fit_mcp/tools/__init__.py",
  "src/professor_fit_mcp/exporters/__init__.py",
  "src/professor_fit_mcp/utils/__init__.py"
)
foreach ($f in $pkgs) { New-Item -Force $f | Out-Null }
```

- [ ] **Step 3: 创建 `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "professor-fit-mcp"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]>=1.6.0",
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=4.9.0",
    "pydantic>=2.0.0",
    "tabulate>=0.9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-httpx>=0.30.0",
]
scholar = ["scholarly>=1.7.0"]

[project.scripts]
professor-fit-mcp = "professor_fit_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/professor_fit_mcp"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.hatch.metadata]
allow-direct-references = true
```

- [ ] **Step 4: 创建 `.gitignore`**

```
__pycache__/
*.pyc
.venv/
dist/
*.egg-info/
.env
professor_fit_cache.db
```

- [ ] **Step 5: 创建 `.env.example`**

```
# OpenAlex 礼貌池（填邮箱后速率更高，非必须）
OPENALEX_EMAIL=your@email.com

# 缓存数据库路径（默认当前目录）
PROFESSOR_FIT_CACHE_PATH=professor_fit_cache.db
```

- [ ] **Step 6: git init 并提交**

```powershell
git init
git add .
git commit -m "chore: initial project scaffolding"
```

---

## Task 2: 数据模型

**Files:**
- Create: `src/professor_fit_mcp/models/common.py`
- Create: `src/professor_fit_mcp/models/paper.py`
- Create: `src/professor_fit_mcp/models/professor.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_models.py
from professor_fit_mcp.models.common import SourcedField
from professor_fit_mcp.models.paper import Paper
from professor_fit_mcp.models.professor import Professor, compute_seniority


def test_sourced_field_defaults():
    f = SourcedField(value=None)
    assert f.confidence == "unknown"
    assert f.sources == []


def test_sourced_field_with_data():
    f = SourcedField(value="Stanford University", sources=["openalex", "homepage"], confidence="high")
    assert f.value == "Stanford University"
    assert len(f.sources) == 2


def test_paper_minimal():
    p = Paper(title="Test Paper", year=2024, source="openalex")
    assert p.title == "Test Paper"
    assert p.abstract is None


def test_professor_minimal():
    prof = Professor(openalex_id="A123", name="Alice Smith")
    assert prof.openalex_id == "A123"
    assert prof.relevance_signal is None
    assert prof.concepts == []


def test_compute_seniority():
    assert compute_seniority(2024) == "new_ap"    # 2 years
    assert compute_seniority(2020) == "early"      # 6 years
    assert compute_seniority(2014) == "mid-career" # 12 years
    assert compute_seniority(2005) == "senior"     # 21 years


def test_professor_dict_serialization():
    prof = Professor(openalex_id="A123", name="Alice Smith")
    d = prof.model_dump()
    assert d["openalex_id"] == "A123"
    assert "recent_papers" in d
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pip install -e ".[dev]"
pytest tests/test_models.py -v
```

预期：`ModuleNotFoundError`

- [ ] **Step 3: 实现 `models/common.py`**

```python
# src/professor_fit_mcp/models/common.py
from typing import Any, Literal
from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low", "unknown"]


class SourcedField(BaseModel):
    """A value with provenance tracking."""
    value: Any = None
    sources: list[str] = Field(default_factory=list)
    confidence: Confidence = "unknown"
```

- [ ] **Step 4: 实现 `models/paper.py`**

```python
# src/professor_fit_mcp/models/paper.py
from typing import Optional
from pydantic import BaseModel


class Paper(BaseModel):
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    url: Optional[str] = None
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    source: str  # "openalex" | "dblp" | "arxiv"
```

- [ ] **Step 5: 实现 `models/professor.py`**

```python
# src/professor_fit_mcp/models/professor.py
from typing import Optional
from pydantic import BaseModel, Field

from .common import SourcedField
from .paper import Paper


def compute_seniority(first_pub_year: int, current_year: int = 2026) -> str:
    """Estimate seniority from first publication year (proxy for academic age)."""
    years = current_year - first_pub_year
    if years <= 3:
        return "new_ap"
    elif years <= 7:
        return "early"
    elif years <= 15:
        return "mid-career"
    else:
        return "senior"


class Professor(BaseModel):
    # --- Identity (primary key = openalex_id) ---
    openalex_id: str
    dblp_pid: Optional[str] = None
    name: str

    # --- Institution ---
    institution: SourcedField = Field(default_factory=SourcedField)
    country_code: Optional[str] = None      # ISO 2-letter from OpenAlex
    institution_tier: Optional[str] = None  # "R1", "985", "Russell", etc.

    # --- Position ---
    position: SourcedField = Field(default_factory=SourcedField)
    is_pi: SourcedField = Field(default_factory=SourcedField)  # bool value

    # --- Academic metrics ---
    h_index: SourcedField = Field(default_factory=SourcedField)
    citation_count: SourcedField = Field(default_factory=SourcedField)
    works_count: Optional[int] = None
    papers_last_3_years: Optional[int] = None

    # --- Seniority (estimated) ---
    first_pub_year: Optional[int] = None   # from DBLP, proxy for academic age
    seniority: Optional[str] = None        # "new_ap"|"early"|"mid-career"|"senior"
    seniority_source: str = "unknown"      # "dblp_estimate" | "unknown"

    # --- Links ---
    homepage_url: Optional[str] = None
    homepage_source: Optional[str] = None        # "dblp" | "openalex"
    homepage_search_query: Optional[str] = None  # for client web-search fallback

    # --- Research ---
    concepts: list[str] = []         # OpenAlex concept display names
    recent_papers: list[Paper] = []  # last 3 years

    # --- Contact (from homepage, best-effort) ---
    email: Optional[str] = None
    lab_name: Optional[str] = None
    lab_url: Optional[str] = None

    # --- Accepting students (best-effort from homepage) ---
    accepting_students_signal: Optional[dict] = None
    # e.g. {"signal": "possibly_open", "snippet": "...", "confidence": "low"}

    # --- Relevance (set by rank_fit) ---
    relevance_signal: Optional[float] = None  # 0.0-1.0
```

- [ ] **Step 6: 运行测试，确认全部通过**

```powershell
pytest tests/test_models.py -v
```

预期：5 tests PASSED

- [ ] **Step 7: Commit**

```powershell
git add src/professor_fit_mcp/models/ tests/test_models.py
git commit -m "feat: add Professor, Paper, SourcedField data models"
```

---

## Task 3: 缓存层

**Files:**
- Create: `src/professor_fit_mcp/utils/cache.py`
- Test: `tests/test_cache.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_cache.py
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
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_cache.py -v
```

预期：`ModuleNotFoundError`

- [ ] **Step 3: 实现 `utils/cache.py`**

```python
# src/professor_fit_mcp/utils/cache.py
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


class Cache:
    """SQLite-backed cache with TTL support.

    Namespaces allow different TTLs for different data types:
    - "professors": 7 days (data changes slowly)
    - "homepage":   1 day  (content changes more often)
    """

    PROFESSOR_TTL = 7 * 24 * 3600   # 7 days
    HOMEPAGE_TTL = 1 * 24 * 3600    # 1 day

    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")  # concurrent read safety
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
        """Return cached value if present and not expired, else None."""
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
        """Store value with given TTL."""
        expires_at = time.time() + ttl_seconds
        value_json = json.dumps(value, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache (namespace, key, value, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (namespace, key, value_json, expires_at),
            )
```

- [ ] **Step 4: 运行测试，确认全部通过**

```powershell
pytest tests/test_cache.py -v
```

预期：5 tests PASSED

- [ ] **Step 5: Commit**

```powershell
git add src/professor_fit_mcp/utils/cache.py tests/test_cache.py
git commit -m "feat: add SQLite cache with TTL and namespace support"
```

---

## Task 4: 文本处理工具

**Files:**
- Create: `src/professor_fit_mcp/utils/text_processing.py`
- Test: `tests/test_text_processing.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_text_processing.py
from professor_fit_mcp.utils.text_processing import whole_word_match, compute_keyword_overlap


def test_whole_word_match_found():
    assert whole_word_match("blockchain", "research on blockchain consensus") is True


def test_whole_word_match_not_found():
    # "security" should not match "AI security" when user means "blockchain security"
    assert whole_word_match("blockchain", "AI security and networking") is False


def test_whole_word_match_no_partial():
    # "block" should NOT match "blockchain"
    assert whole_word_match("block", "blockchain research") is False


def test_whole_word_match_case_insensitive():
    assert whole_word_match("Blockchain", "Recent BLOCKCHAIN work") is True


def test_compute_keyword_overlap_full():
    score = compute_keyword_overlap(
        keywords=["blockchain", "consensus"],
        corpus="blockchain consensus protocol research",
    )
    assert score == 1.0


def test_compute_keyword_overlap_partial():
    score = compute_keyword_overlap(
        keywords=["blockchain", "consensus", "MEV"],
        corpus="blockchain research and consensus",
    )
    assert abs(score - 2/3) < 0.01


def test_compute_keyword_overlap_empty_keywords():
    score = compute_keyword_overlap(keywords=[], corpus="anything")
    assert score == 0.0


def test_compute_keyword_overlap_empty_corpus():
    score = compute_keyword_overlap(keywords=["blockchain"], corpus="")
    assert score == 0.0
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_text_processing.py -v
```

- [ ] **Step 3: 实现 `utils/text_processing.py`**

```python
# src/professor_fit_mcp/utils/text_processing.py
import re


def whole_word_match(keyword: str, text: str) -> bool:
    """Case-insensitive whole-word search. Avoids substring false positives."""
    pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
    return bool(re.search(pattern, text.lower()))


def compute_keyword_overlap(keywords: list[str], corpus: str) -> float:
    """
    Fraction of keywords found in corpus via whole-word matching.
    Returns 0.0 if keywords is empty.
    """
    if not keywords or not corpus:
        return 0.0
    matched = sum(1 for kw in keywords if whole_word_match(kw, corpus))
    return matched / len(keywords)
```

- [ ] **Step 4: 运行测试，确认全部通过**

```powershell
pytest tests/test_text_processing.py -v
```

预期：8 tests PASSED

- [ ] **Step 5: Commit**

```powershell
git add src/professor_fit_mcp/utils/text_processing.py tests/test_text_processing.py
git commit -m "feat: add whole-word keyword matching utilities"
```

---

## Task 5: 院校分级数据 + 分类器

**Files:**
- Create: `data/institutions/*.json`
- Create: `src/professor_fit_mcp/services/institution.py`
- Test: `tests/test_institution.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_institution.py
from professor_fit_mcp.services.institution import InstitutionClassifier


def test_us_r1_recognized():
    clf = InstitutionClassifier()
    result = clf.classify("Massachusetts Institute of Technology", "US")
    assert result["tier"] == "R1"


def test_cn_985_recognized():
    clf = InstitutionClassifier()
    result = clf.classify("Tsinghua University", "CN")
    assert result["tier"] == "985"


def test_uk_russell_recognized():
    clf = InstitutionClassifier()
    result = clf.classify("University of Oxford", "GB")
    assert result["tier"] == "Russell"


def test_unknown_institution():
    clf = InstitutionClassifier()
    result = clf.classify("Unknown Small College", "US")
    assert result["tier"] is None


def test_case_insensitive():
    clf = InstitutionClassifier()
    result = clf.classify("stanford university", "US")
    assert result["tier"] == "R1"
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_institution.py -v
```

- [ ] **Step 3: 创建院校 JSON 数据文件**

`data/institutions/us_r1.json`（部分示例，含主要 R1 院校）:
```json
[
  "Massachusetts Institute of Technology",
  "Stanford University",
  "Harvard University",
  "Carnegie Mellon University",
  "University of California, Berkeley",
  "California Institute of Technology",
  "Princeton University",
  "Columbia University",
  "University of Michigan",
  "University of Illinois Urbana-Champaign",
  "Cornell University",
  "University of Washington",
  "University of Texas at Austin",
  "Georgia Institute of Technology",
  "Purdue University",
  "University of Wisconsin-Madison",
  "University of California, Los Angeles",
  "University of California, San Diego",
  "New York University",
  "Boston University",
  "Duke University",
  "University of Pennsylvania",
  "Yale University",
  "Johns Hopkins University",
  "Northwestern University",
  "University of Southern California",
  "Rice University",
  "Vanderbilt University",
  "University of Minnesota",
  "Ohio State University"
]
```

`data/institutions/cn_985_211.json`:
```json
{
  "985": [
    "Peking University",
    "Tsinghua University",
    "Fudan University",
    "Shanghai Jiao Tong University",
    "Zhejiang University",
    "University of Science and Technology of China",
    "Nanjing University",
    "Harbin Institute of Technology",
    "Xi'an Jiaotong University",
    "Wuhan University",
    "Sun Yat-sen University",
    "Huazhong University of Science and Technology",
    "Tongji University",
    "Tianjin University",
    "Beihang University",
    "Beijing Institute of Technology",
    "Southeast University",
    "South China University of Technology",
    "Northwestern Polytechnical University",
    "Shandong University"
  ],
  "211": [
    "Beijing Jiaotong University",
    "Beijing University of Posts and Telecommunications",
    "Central South University",
    "Dalian University of Technology",
    "Jilin University",
    "Lanzhou University",
    "Northeastern University",
    "Renmin University of China",
    "Xiamen University"
  ]
}
```

`data/institutions/uk_russell.json`:
```json
[
  "University of Oxford",
  "University of Cambridge",
  "Imperial College London",
  "University College London",
  "University of Edinburgh",
  "University of Manchester",
  "University of Bristol",
  "University of Warwick",
  "University of Glasgow",
  "University of Birmingham",
  "University of Leeds",
  "University of Sheffield",
  "University of Nottingham",
  "University of Southampton",
  "Queen Mary University of London",
  "King's College London",
  "Newcastle University",
  "Cardiff University",
  "University of Liverpool",
  "London School of Economics and Political Science",
  "Queen's University Belfast",
  "University of Exeter"
]
```

`data/institutions/au_go8.json`:
```json
[
  "University of Melbourne",
  "Australian National University",
  "University of Sydney",
  "University of Queensland",
  "University of Western Australia",
  "University of Adelaide",
  "Monash University",
  "University of New South Wales"
]
```

`data/institutions/ca_u15.json`:
```json
[
  "University of Toronto",
  "McGill University",
  "University of British Columbia",
  "University of Alberta",
  "University of Montreal",
  "University of Waterloo",
  "McMaster University",
  "University of Ottawa",
  "Western University",
  "Queen's University",
  "Dalhousie University",
  "University of Manitoba",
  "University of Saskatchewan",
  "University of Calgary",
  "Laval University"
]
```

`data/institutions/de_tu9.json`:
```json
[
  "RWTH Aachen University",
  "Technical University of Berlin",
  "Technical University of Braunschweig",
  "Technical University of Darmstadt",
  "Technical University of Dresden",
  "University of Hannover",
  "Karlsruhe Institute of Technology",
  "Technical University of Munich",
  "University of Stuttgart"
]
```

`data/institutions/jp_imperial.json`:
```json
[
  "University of Tokyo",
  "Kyoto University",
  "Osaka University",
  "Tohoku University",
  "Nagoya University",
  "Kyushu University",
  "Hokkaido University"
]
```

`data/institutions/kr_sky.json`:
```json
[
  "Seoul National University",
  "Yonsei University",
  "Korea University",
  "Korea Advanced Institute of Science and Technology",
  "Pohang University of Science and Technology"
]
```

- [ ] **Step 4: 实现 `services/institution.py`**

```python
# src/professor_fit_mcp/services/institution.py
import json
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "institutions"


class InstitutionClassifier:
    """Classify an institution into a tier (R1, 985, Russell, etc.)."""

    def __init__(self, data_dir: Path = _DATA_DIR):
        self._index: dict[str, dict] = {}  # lowercased_name -> {tier, country}
        self._load(data_dir)

    def _load(self, data_dir: Path) -> None:
        configs = [
            ("us_r1.json",      "R1",      "US"),
            ("uk_russell.json", "Russell", "GB"),
            ("au_go8.json",     "Go8",     "AU"),
            ("ca_u15.json",     "U15",     "CA"),
            ("de_tu9.json",     "TU9",     "DE"),
            ("jp_imperial.json","Imperial","JP"),
            ("kr_sky.json",     "SKY",     "KR"),
        ]
        for filename, tier, country in configs:
            path = data_dir / filename
            if not path.exists():
                continue
            names: list[str] = json.loads(path.read_text(encoding="utf-8"))
            for name in names:
                self._index[name.lower()] = {"tier": tier, "country": country}

        # CN has nested 985/211 structure
        cn_path = data_dir / "cn_985_211.json"
        if cn_path.exists():
            data = json.loads(cn_path.read_text(encoding="utf-8"))
            for tier, names in data.items():
                for name in names:
                    self._index[name.lower()] = {"tier": tier.upper(), "country": "CN"}

    def classify(self, institution_name: str, country_code: Optional[str] = None) -> dict:
        """
        Returns {"tier": str | None, "country": str | None}.
        Tier is None if institution not in known lists.
        """
        key = institution_name.lower().strip()
        entry = self._index.get(key)
        if entry:
            return {"tier": entry["tier"], "country": entry["country"]}
        return {"tier": None, "country": country_code}
```

- [ ] **Step 5: 运行测试，确认全部通过**

```powershell
pytest tests/test_institution.py -v
```

预期：5 tests PASSED

- [ ] **Step 6: Commit**

```powershell
git add data/ src/professor_fit_mcp/services/institution.py tests/test_institution.py
git commit -m "feat: add institution tier classifier with R1/985/Russell/Go8 data"
```

---

## Task 6: OpenAlex 服务

**Files:**
- Create: `src/professor_fit_mcp/services/openalex.py`
- Test: `tests/test_openalex.py`

OpenAlex 免费 API，无 key，提供「礼貌池」（填 email 后速率更高）。

关键端点：
- 作者搜索：`GET https://api.openalex.org/authors?search={name}`
- 作者详情：`GET https://api.openalex.org/authors/{id}`
- 近期论文：`GET https://api.openalex.org/works?filter=authorships.author.id:{id},publication_year:>={year}`

- [ ] **Step 1: 写失败的测试（使用 httpx mock 不真实请求）**

```python
# tests/test_openalex.py
import pytest
import httpx
from pytest_httpx import HTTPXMock
from professor_fit_mcp.services.openalex import OpenAlexService


@pytest.fixture
def svc():
    return OpenAlexService(email="test@example.com")


def _author_response():
    return {
        "results": [
            {
                "id": "https://openalex.org/A123456",
                "display_name": "Percy Liang",
                "last_known_institutions": [
                    {"display_name": "Stanford University", "country_code": "US", "type": "education"}
                ],
                "summary_stats": {"h_index": 85, "i10_index": 120},
                "cited_by_count": 25000,
                "works_count": 150,
                "counts_by_year": [
                    {"year": 2024, "works_count": 8},
                    {"year": 2023, "works_count": 10},
                    {"year": 2022, "works_count": 9},
                ],
                "x_concepts": [
                    {"display_name": "Natural Language Processing", "score": 0.9},
                    {"display_name": "Machine Learning", "score": 0.8},
                ],
                "homepage_url": "https://cs.stanford.edu/~pliang/",
            }
        ]
    }


def _works_response():
    return {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Holistic Evaluation of Language Models",
                "publication_year": 2024,
                "primary_location": {"source": {"display_name": "NeurIPS"}},
                "abstract_inverted_index": None,
                "authorships": [{"author": {"display_name": "Percy Liang"}}],
                "doi": "10.1234/test",
                "ids": {"arxiv": "https://arxiv.org/abs/2211.09110"},
            }
        ]
    }


def test_search_authors(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(
        url__contains="openalex.org/authors",
        json=_author_response(),
    )
    import asyncio
    results = asyncio.run(svc.search_authors("Percy Liang"))
    assert len(results) == 1
    assert results[0]["openalex_id"] == "A123456"
    assert results[0]["name"] == "Percy Liang"
    assert results[0]["h_index"] == 85
    assert results[0]["institution"] == "Stanford University"
    assert results[0]["country_code"] == "US"
    assert results[0]["concepts"] == ["Natural Language Processing", "Machine Learning"]
    assert results[0]["homepage_url"] == "https://cs.stanford.edu/~pliang/"


def test_get_recent_works(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(
        url__contains="openalex.org/works",
        json=_works_response(),
    )
    import asyncio
    papers = asyncio.run(svc.get_recent_works("A123456", since_year=2022))
    assert len(papers) == 1
    assert papers[0].title == "Holistic Evaluation of Language Models"
    assert papers[0].year == 2024
    assert papers[0].source == "openalex"
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_openalex.py -v
```

- [ ] **Step 3: 实现 `services/openalex.py`**

```python
# src/professor_fit_mcp/services/openalex.py
import os
from typing import Optional
import httpx

from ..models.paper import Paper

_BASE = "https://api.openalex.org"
_DEFAULT_EMAIL = os.getenv("OPENALEX_EMAIL", "")
_TIMEOUT = 15.0
_MAX_CONCURRENT = 5  # polite pool limit


def _extract_id(openalex_url: str) -> str:
    """'https://openalex.org/A123456' -> 'A123456'"""
    return openalex_url.rstrip("/").split("/")[-1]


def _parse_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return None
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    if not words:
        return None
    return " ".join(words[i] for i in sorted(words))


class OpenAlexService:
    def __init__(self, email: str = _DEFAULT_EMAIL):
        self._email = email

    def _params(self, extra: Optional[dict] = None) -> dict:
        p: dict = {}
        if self._email:
            p["mailto"] = self._email
        if extra:
            p.update(extra)
        return p

    async def search_authors(
        self,
        name: str,
        institution: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search authors by name. Returns list of structured author dicts."""
        params = self._params({
            "search": name,
            "per_page": min(limit, 50),
        })
        if institution:
            params["filter"] = (
                f"last_known_institutions.display_name.search:{institution}"
            )

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE}/authors", params=params)
            resp.raise_for_status()
        return [self._parse_author(a) for a in resp.json().get("results", [])]

    async def get_author(self, openalex_id: str) -> Optional[dict]:
        """Fetch full author record by OpenAlex ID (e.g. 'A123456')."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_BASE}/authors/{openalex_id}",
                params=self._params(),
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
        return self._parse_author(resp.json())

    async def get_recent_works(
        self,
        openalex_id: str,
        since_year: int = 2023,
        limit: int = 50,
    ) -> list[Paper]:
        """Fetch recent works (>= since_year) for an author."""
        params = self._params({
            "filter": f"authorships.author.id:{openalex_id},publication_year:>={since_year}",
            "per_page": min(limit, 50),
            "select": "id,title,publication_year,primary_location,abstract_inverted_index,"
                      "authorships,doi,ids",
        })
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_BASE}/works", params=params)
            resp.raise_for_status()
        return [self._parse_work(w) for w in resp.json().get("results", [])]

    def _parse_author(self, raw: dict) -> dict:
        openalex_url = raw.get("id", "")
        openalex_id = _extract_id(openalex_url) if openalex_url else ""

        institutions = raw.get("last_known_institutions") or []
        inst = institutions[0] if institutions else {}

        concepts = [
            c["display_name"]
            for c in (raw.get("x_concepts") or [])
            if c.get("score", 0) > 0.3
        ]

        counts_by_year: list[dict] = raw.get("counts_by_year") or []
        recent_years = {c["year"] for c in counts_by_year if c["year"] >= 2023}
        papers_last_3y = sum(
            c["works_count"] for c in counts_by_year if c["year"] >= 2023
        )

        stats = raw.get("summary_stats") or {}

        return {
            "openalex_id": openalex_id,
            "name": raw.get("display_name", ""),
            "institution": inst.get("display_name"),
            "country_code": inst.get("country_code"),
            "institution_type": inst.get("type"),
            "h_index": stats.get("h_index"),
            "citation_count": raw.get("cited_by_count"),
            "works_count": raw.get("works_count"),
            "papers_last_3_years": papers_last_3y if recent_years else None,
            "concepts": concepts,
            "homepage_url": raw.get("homepage_url"),
        }

    def _parse_work(self, raw: dict) -> Paper:
        location = raw.get("primary_location") or {}
        source = location.get("source") or {}
        venue = source.get("display_name")

        ids = raw.get("ids") or {}
        arxiv_url = ids.get("arxiv") or ""
        arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else None

        authors = [
            a["author"]["display_name"]
            for a in (raw.get("authorships") or [])
            if a.get("author", {}).get("display_name")
        ]

        return Paper(
            title=raw.get("title") or "",
            authors=authors,
            year=raw.get("publication_year"),
            venue=venue,
            abstract=_parse_abstract(raw.get("abstract_inverted_index")),
            doi=raw.get("doi"),
            arxiv_id=arxiv_id,
            url=arxiv_url or raw.get("doi"),
            source="openalex",
        )
```

- [ ] **Step 4: 运行测试，确认全部通过**

```powershell
pytest tests/test_openalex.py -v
```

预期：2 tests PASSED

- [ ] **Step 5: Commit**

```powershell
git add src/professor_fit_mcp/services/openalex.py tests/test_openalex.py
git commit -m "feat: add OpenAlex service (author search, details, recent works)"
```

---

## Task 7: DBLP 服务

**Files:**
- Create: `src/professor_fit_mcp/services/dblp.py`
- Test: `tests/test_dblp.py`

DBLP person search API（免费，无 key）：
- 搜索人名：`GET https://dblp.org/search/author/api?q={name}&format=json`
- 获取 person XML（含 homepage URL 和 note 字段）：`GET https://dblp.org/pid/{pid}.xml`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_dblp.py
import pytest
from pytest_httpx import HTTPXMock
from professor_fit_mcp.services.dblp import DBLPService


@pytest.fixture
def svc():
    return DBLPService()


_SEARCH_RESPONSE = {
    "result": {
        "hits": {
            "@sent": "1",
            "hit": [
                {
                    "@score": "4",
                    "info": {
                        "author": "Percy Liang",
                        "url": "https://dblp.org/pid/46/5782",
                    },
                }
            ],
        }
    }
}

_PERSON_XML = """<?xml version="1.0"?>
<dblpperson name="Percy Liang" pid="46/5782" n="150">
  <note type="source:homepage">https://cs.stanford.edu/~pliang/</note>
  <r><article key="journals/corr/Liang2023" mdate="2023-01-01">
    <author>Percy Liang</author>
    <year>2023</year>
  </article></r>
  <r><article key="journals/corr/Liang2010" mdate="2010-01-01">
    <year>2010</year>
  </article></r>
</dblpperson>"""


def test_search_person(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(
        url__contains="dblp.org/search/author",
        json=_SEARCH_RESPONSE,
    )
    import asyncio
    results = asyncio.run(svc.search_person("Percy Liang"))
    assert len(results) == 1
    assert results[0]["pid"] == "46/5782"
    assert results[0]["name"] == "Percy Liang"


def test_get_person_record(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(
        url__contains="dblp.org/pid",
        text=_PERSON_XML,
        headers={"content-type": "application/xml"},
    )
    import asyncio
    record = asyncio.run(svc.get_person_record("46/5782"))
    assert record["homepage_url"] == "https://cs.stanford.edu/~pliang/"
    assert record["first_pub_year"] == 2010
    assert record["pid"] == "46/5782"
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_dblp.py -v
```

- [ ] **Step 3: 实现 `services/dblp.py`**

```python
# src/professor_fit_mcp/services/dblp.py
from typing import Optional
import httpx
from bs4 import BeautifulSoup

_TIMEOUT = 10.0


class DBLPService:
    """DBLP person search — finds homepage URL and first publication year."""

    async def search_person(
        self,
        name: str,
        limit: int = 5,
    ) -> list[dict]:
        """Search DBLP for a person by name. Returns list of {pid, name, url}."""
        params = {"q": name, "format": "json", "h": str(limit)}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://dblp.org/search/author/api", params=params
            )
            resp.raise_for_status()

        hits = (
            resp.json()
            .get("result", {})
            .get("hits", {})
            .get("hit", [])
        )
        if isinstance(hits, dict):
            hits = [hits]  # single result comes as dict, not list

        results = []
        for hit in hits:
            info = hit.get("info", {})
            dblp_url = info.get("url", "")
            # Extract PID from URL: "https://dblp.org/pid/46/5782" -> "46/5782"
            pid = "/".join(dblp_url.split("/pid/")[-1].split("/")[:2]) if "/pid/" in dblp_url else ""
            results.append({"pid": pid, "name": info.get("author", ""), "dblp_url": dblp_url})
        return results

    async def get_person_record(self, pid: str) -> dict:
        """
        Fetch DBLP person XML and extract:
        - homepage_url (from <note type="source:homepage">)
        - first_pub_year (earliest year in publication list)
        """
        url = f"https://dblp.org/pid/{pid}.xml"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml-xml")

        # Homepage URL
        note = soup.find("note", {"type": "source:homepage"})
        homepage_url = note.get_text(strip=True) if note else None

        # First publication year
        years = [
            int(y.get_text(strip=True))
            for y in soup.find_all("year")
            if y.get_text(strip=True).isdigit()
        ]
        first_pub_year = min(years) if years else None

        return {
            "pid": pid,
            "homepage_url": homepage_url,
            "first_pub_year": first_pub_year,
        }
```

- [ ] **Step 4: 运行测试，确认全部通过**

```powershell
pytest tests/test_dblp.py -v
```

预期：2 tests PASSED

- [ ] **Step 5: Commit**

```powershell
git add src/professor_fit_mcp/services/dblp.py tests/test_dblp.py
git commit -m "feat: add DBLP service (person search, homepage URL, first pub year)"
```

---

## Task 8: 主页抓取服务

**Files:**
- Create: `src/professor_fit_mcp/services/homepage.py`
- Test: `tests/test_homepage.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_homepage.py
import pytest
from pytest_httpx import HTTPXMock
from professor_fit_mcp.services.homepage import HomepageService

_HTML_WITH_PROF = """
<html>
<head><title>Alice Smith - Associate Professor</title></head>
<body>
  <h1>Alice Smith</h1>
  <p>Associate Professor of Computer Science</p>
  <p>Email: <a href="mailto:alice@cs.example.edu">alice@cs.example.edu</a></p>
  <p><a href="https://ailab.example.edu">AI Research Lab</a></p>
  <p>I am looking for motivated PhD students to join my group.</p>
</body>
</html>
"""

_HTML_MINIMAL = """
<html><body><p>No useful info here.</p></body></html>
"""


@pytest.fixture
def svc():
    return HomepageService()


def test_extract_position(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/alice", text=_HTML_WITH_PROF)
    import asyncio
    result = asyncio.run(svc.fetch("https://example.edu/alice"))
    assert result["position"] == "Associate Professor"


def test_extract_email(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/alice", text=_HTML_WITH_PROF)
    import asyncio
    result = asyncio.run(svc.fetch("https://example.edu/alice"))
    assert result["email"] == "alice@cs.example.edu"


def test_extract_accepting_students_signal(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/alice", text=_HTML_WITH_PROF)
    import asyncio
    result = asyncio.run(svc.fetch("https://example.edu/alice"))
    assert result["accepting_signal"] is not None
    assert result["accepting_signal"]["signal"] == "possibly_open"
    assert "looking for" in result["accepting_signal"]["snippet"].lower()


def test_no_position_found(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/min", text=_HTML_MINIMAL)
    import asyncio
    result = asyncio.run(svc.fetch("https://example.edu/min"))
    assert result["position"] is None
    assert result["email"] is None
    assert result["accepting_signal"] is None


def test_fetch_error_returns_empty(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/bad", status_code=404)
    import asyncio
    result = asyncio.run(svc.fetch("https://example.edu/bad"))
    assert result["position"] is None
    assert result["error"] is not None
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_homepage.py -v
```

- [ ] **Step 3: 实现 `services/homepage.py`**

```python
# src/professor_fit_mcp/services/homepage.py
import re
from typing import Optional
import httpx
from bs4 import BeautifulSoup

_TIMEOUT = 10.0

_POSITION_PATTERNS = [
    r"(full\s+professor)",
    r"(associate\s+professor)",
    r"(assistant\s+professor)",
    r"(professor\s+of\s+\w+)",
    r"(research\s+scientist)",
    r"(principal\s+investigator)",
]
_POSITION_RE = re.compile(
    "|".join(_POSITION_PATTERNS), re.IGNORECASE
)

_ACCEPTING_KEYWORDS = [
    "looking for",
    "seeking",
    "recruiting",
    "accepting applications",
    "open positions",
    "phd openings",
    "graduate students",
    "开放招生",
    "招收",
]


class HomepageService:
    """Best-effort extraction from a professor's personal homepage."""

    async def fetch(self, url: str) -> dict:
        """
        Returns dict with keys:
          position, email, lab_name, lab_url, accepting_signal, error
        All keys present; values None if not found.
        """
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "ProfessorFitMCP/0.1 (academic research tool)"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
            html = resp.text
        except Exception as exc:
            return self._empty(error=str(exc))

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        return {
            "position": self._extract_position(text),
            "email": self._extract_email(soup),
            "lab_name": self._extract_lab_name(soup),
            "lab_url": self._extract_lab_url(soup, url),
            "accepting_signal": self._extract_accepting_signal(text),
            "error": None,
        }

    def _extract_position(self, text: str) -> Optional[str]:
        m = _POSITION_RE.search(text)
        if m:
            return m.group(0).strip()
        return None

    def _extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        link = soup.find("a", href=re.compile(r"^mailto:", re.I))
        if link:
            return link["href"].replace("mailto:", "").strip().split("?")[0]
        # Fallback: look for email pattern in text
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", soup.get_text())
        return m.group(0) if m else None

    def _extract_lab_name(self, soup: BeautifulSoup) -> Optional[str]:
        lab_link = soup.find("a", string=re.compile(r"lab|group|center|institute", re.I))
        if lab_link:
            return lab_link.get_text(strip=True)
        return None

    def _extract_lab_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        lab_link = soup.find("a", href=re.compile(r"lab|group|center|institute", re.I))
        if lab_link:
            href = lab_link.get("href", "")
            if href.startswith("http"):
                return href
        return None

    def _extract_accepting_signal(self, text: str) -> Optional[dict]:
        lower = text.lower()
        for kw in _ACCEPTING_KEYWORDS:
            idx = lower.find(kw)
            if idx != -1:
                # Extract surrounding snippet (up to 150 chars)
                start = max(0, idx - 20)
                end = min(len(text), idx + len(kw) + 130)
                snippet = text[start:end].strip()
                return {
                    "signal": "possibly_open",
                    "snippet": snippet,
                    "confidence": "low",
                }
        return None

    def _empty(self, error: str) -> dict:
        return {
            "position": None,
            "email": None,
            "lab_name": None,
            "lab_url": None,
            "accepting_signal": None,
            "error": error,
        }
```

- [ ] **Step 4: 运行测试，确认全部通过**

```powershell
pytest tests/test_homepage.py -v
```

预期：5 tests PASSED

- [ ] **Step 5: Commit**

```powershell
git add src/professor_fit_mcp/services/homepage.py tests/test_homepage.py
git commit -m "feat: add homepage service (position, email, lab, accepting signal)"
```

---

## Task 9: search_professors 工具

**Files:**
- Create: `src/professor_fit_mcp/tools/search.py`
- Test: `tests/test_tools_search.py`

组合 OpenAlex 搜索 + DBLP 主页 URL + 院校分级，返回候选列表。

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_tools_search.py
import pytest
from unittest.mock import AsyncMock, patch
from professor_fit_mcp.tools.search import search_professors_impl


@pytest.fixture
def mock_openalex_results():
    return [
        {
            "openalex_id": "A123",
            "name": "Alice Smith",
            "institution": "Massachusetts Institute of Technology",
            "country_code": "US",
            "institution_type": "education",
            "h_index": 65,
            "citation_count": 18000,
            "works_count": 120,
            "papers_last_3_years": 12,
            "concepts": ["Machine Learning", "Blockchain"],
            "homepage_url": None,
        }
    ]


@pytest.mark.asyncio
async def test_search_returns_professors(mock_openalex_results):
    with patch(
        "professor_fit_mcp.tools.search.OpenAlexService.search_authors",
        new=AsyncMock(return_value=mock_openalex_results),
    ):
        result = await search_professors_impl(
            keywords=["blockchain", "machine learning"],
            limit=10,
        )
    assert len(result["professors"]) == 1
    prof = result["professors"][0]
    assert prof["openalex_id"] == "A123"
    assert prof["name"] == "Alice Smith"
    assert prof["institution_tier"] == "R1"


@pytest.mark.asyncio
async def test_search_adds_homepage_search_query(mock_openalex_results):
    with patch(
        "professor_fit_mcp.tools.search.OpenAlexService.search_authors",
        new=AsyncMock(return_value=mock_openalex_results),
    ):
        result = await search_professors_impl(keywords=["blockchain"])
    prof = result["professors"][0]
    # No homepage_url → should have search_query for client fallback
    assert prof["homepage_url"] is None
    assert "Alice Smith" in prof["homepage_search_query"]
    assert "MIT" in prof["homepage_search_query"] or "Massachusetts" in prof["homepage_search_query"]


@pytest.mark.asyncio
async def test_search_region_filter():
    cn_result = [{
        "openalex_id": "B456",
        "name": "Bob Zhang",
        "institution": "Tsinghua University",
        "country_code": "CN",
        "institution_type": "education",
        "h_index": 40,
        "citation_count": 5000,
        "works_count": 80,
        "papers_last_3_years": 8,
        "concepts": ["Blockchain"],
        "homepage_url": None,
    }]
    with patch(
        "professor_fit_mcp.tools.search.OpenAlexService.search_authors",
        new=AsyncMock(return_value=cn_result),
    ):
        result = await search_professors_impl(
            keywords=["blockchain"],
            regions=["US"],  # Only US
        )
    # CN professor should be filtered out
    assert len(result["professors"]) == 0
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_tools_search.py -v
```

- [ ] **Step 3: 实现 `tools/search.py`**

```python
# src/professor_fit_mcp/tools/search.py
import os
from pathlib import Path
from typing import Optional

from ..services.openalex import OpenAlexService
from ..services.institution import InstitutionClassifier
from ..utils.cache import Cache

_cache = Cache(Path(os.getenv("PROFESSOR_FIT_CACHE_PATH", "professor_fit_cache.db")))
_institution_clf = InstitutionClassifier()

# Country code normalization map
_REGION_ALIASES = {
    "US": ["US"],
    "UK": ["GB"],
    "GB": ["GB"],
    "CN": ["CN"],
    "JP": ["JP"],
    "KR": ["KR"],
    "DE": ["DE"],
    "CA": ["CA"],
    "AU": ["AU"],
    "SG": ["SG"],
    "HK": ["HK"],
    "ASIA": ["CN", "JP", "KR", "SG", "HK", "TW"],
    "ALL": None,  # no filter
}


def _normalize_regions(regions: Optional[list[str]]) -> Optional[set[str]]:
    """Expand region aliases to ISO country codes. None means no filter."""
    if not regions:
        return None
    codes: set[str] = set()
    for r in regions:
        expanded = _REGION_ALIASES.get(r.upper())
        if expanded is None:
            return None  # "ALL" → no filter
        codes.update(expanded)
    return codes


async def search_professors_impl(
    keywords: list[str],
    paper_url: Optional[str] = None,
    regions: Optional[list[str]] = None,
    university_filter: Optional[list[str]] = None,
    institution_tier: Optional[list[str]] = None,
    limit: int = 20,
) -> dict:
    """Core logic for search_professors MCP tool."""
    svc = OpenAlexService()
    allowed_countries = _normalize_regions(regions)

    # Build combined search query from keywords
    query = " ".join(keywords)

    # Check cache
    cache_key = f"search:{query}:{limit}"
    cached = _cache.get(cache_key, "professors")
    raw_results = cached if cached else await svc.search_authors(query, limit=limit * 2)
    if not cached:
        _cache.set(cache_key, raw_results, "professors", ttl_seconds=Cache.PROFESSOR_TTL)

    professors = []
    for raw in raw_results:
        country = raw.get("country_code")

        # Region filter
        if allowed_countries is not None and country not in allowed_countries:
            continue

        # Institution tier filter
        inst_name = raw.get("institution") or ""
        tier_info = _institution_clf.classify(inst_name, country)
        tier = tier_info.get("tier")

        if institution_tier and tier not in institution_tier:
            continue

        # University filter (substring match)
        if university_filter:
            if not any(f.lower() in inst_name.lower() for f in university_filter):
                continue

        # Build homepage search query for client fallback
        homepage_url = raw.get("homepage_url")
        search_query = None
        if not homepage_url:
            search_query = f"{raw['name']} {inst_name} homepage"

        prof = {
            "openalex_id": raw["openalex_id"],
            "name": raw["name"],
            "institution": inst_name,
            "country_code": country,
            "institution_tier": tier,
            "h_index": raw.get("h_index"),
            "citation_count": raw.get("citation_count"),
            "works_count": raw.get("works_count"),
            "papers_last_3_years": raw.get("papers_last_3_years"),
            "concepts": raw.get("concepts", []),
            "homepage_url": homepage_url,
            "homepage_search_query": search_query,
            "source": "openalex",
        }
        professors.append(prof)

        if len(professors) >= limit:
            break

    return {
        "professors": professors,
        "total_found": len(professors),
        "query": query,
    }
```

- [ ] **Step 4: 运行测试，确认全部通过**

```powershell
pytest tests/test_tools_search.py -v
```

预期：3 tests PASSED

- [ ] **Step 5: Commit**

```powershell
git add src/professor_fit_mcp/tools/search.py tests/test_tools_search.py
git commit -m "feat: add search_professors tool (OpenAlex + tier filter + region filter)"
```

---

## Task 10: get_professor_details 工具

**Files:**
- Create: `src/professor_fit_mcp/tools/details.py`
- Test: `tests/test_tools_details.py`

多源聚合：OpenAlex 基础信息 + DBLP 主页/首发年 + 主页抓取 + 院校分级 + SourcedField 溯源。

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_tools_details.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from professor_fit_mcp.tools.details import get_professor_details_impl


@pytest.mark.asyncio
async def test_details_from_openalex_and_dblp():
    openalex_author = {
        "openalex_id": "A123",
        "name": "Alice Smith",
        "institution": "Stanford University",
        "country_code": "US",
        "institution_type": "education",
        "h_index": 85,
        "citation_count": 25000,
        "works_count": 150,
        "papers_last_3_years": 10,
        "concepts": ["Machine Learning", "NLP"],
        "homepage_url": None,
    }
    dblp_search = [{"pid": "46/0001", "name": "Alice Smith", "dblp_url": "..."}]
    dblp_record = {
        "pid": "46/0001",
        "homepage_url": "https://cs.stanford.edu/~alice/",
        "first_pub_year": 2012,
    }
    homepage_data = {
        "position": "Associate Professor",
        "email": "alice@cs.stanford.edu",
        "lab_name": "AI Lab",
        "lab_url": "https://ailab.stanford.edu",
        "accepting_signal": None,
        "error": None,
    }

    with (
        patch("professor_fit_mcp.tools.details.OpenAlexService.get_author",
              new=AsyncMock(return_value=openalex_author)),
        patch("professor_fit_mcp.tools.details.DBLPService.search_person",
              new=AsyncMock(return_value=dblp_search)),
        patch("professor_fit_mcp.tools.details.DBLPService.get_person_record",
              new=AsyncMock(return_value=dblp_record)),
        patch("professor_fit_mcp.tools.details.HomepageService.fetch",
              new=AsyncMock(return_value=homepage_data)),
    ):
        result = await get_professor_details_impl(professor_id="A123")

    assert result["openalex_id"] == "A123"
    assert result["name"] == "Alice Smith"
    assert result["h_index"]["value"] == 85
    assert result["h_index"]["sources"] == ["openalex"]
    assert result["h_index"]["confidence"] == "high"
    assert result["position"]["value"] == "Associate Professor"
    assert result["position"]["sources"] == ["homepage"]
    assert result["homepage_url"] == "https://cs.stanford.edu/~alice/"
    assert result["homepage_source"] == "dblp"
    assert result["seniority"] == "mid-career"  # 2026 - 2012 = 14 years
    assert result["email"] == "alice@cs.stanford.edu"
    assert result["institution_tier"] == "R1"
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_tools_details.py -v
```

- [ ] **Step 3: 实现 `tools/details.py`**

```python
# src/professor_fit_mcp/tools/details.py
import os
from pathlib import Path
from typing import Optional

from ..services.openalex import OpenAlexService
from ..services.dblp import DBLPService
from ..services.homepage import HomepageService
from ..services.institution import InstitutionClassifier
from ..models.professor import Professor, compute_seniority
from ..models.common import SourcedField
from ..utils.cache import Cache

_cache = Cache(Path(os.getenv("PROFESSOR_FIT_CACHE_PATH", "professor_fit_cache.db")))
_institution_clf = InstitutionClassifier()


def _sourced(value, sources: list[str], confidence: str) -> dict:
    return {"value": value, "sources": sources, "confidence": confidence}


async def get_professor_details_impl(
    professor_id: Optional[str] = None,
    name: Optional[str] = None,
    university: Optional[str] = None,
) -> dict:
    """
    Multi-source professor profile assembly:
    OpenAlex (primary) + DBLP (homepage URL, first_pub_year) + homepage (position, email, lab).
    """
    # --- 1. Fetch OpenAlex author ---
    oa_svc = OpenAlexService()
    if professor_id:
        oa_author = await oa_svc.get_author(professor_id)
    elif name:
        results = await oa_svc.search_authors(name, institution=university, limit=1)
        oa_author = results[0] if results else None
    else:
        raise ValueError("Must provide professor_id or name")

    if not oa_author:
        return {"error": "Professor not found in OpenAlex"}

    openalex_id = oa_author["openalex_id"]

    # Check detail cache
    cached = _cache.get(openalex_id, "professor_details")
    if cached:
        return cached

    # --- 2. Fetch recent papers from OpenAlex ---
    recent_papers = await oa_svc.get_recent_works(openalex_id, since_year=2023)

    # --- 3. Fetch DBLP person record ---
    dblp_svc = DBLPService()
    dblp_record = None
    search_name = oa_author.get("name", name or "")
    dblp_results = await dblp_svc.search_person(search_name, limit=3)
    # Pick best match: same institution or first result
    if dblp_results:
        dblp_record = await dblp_svc.get_person_record(dblp_results[0]["pid"])

    # --- 4. Determine homepage URL (DBLP > OpenAlex) ---
    homepage_url = None
    homepage_source = None
    if dblp_record and dblp_record.get("homepage_url"):
        homepage_url = dblp_record["homepage_url"]
        homepage_source = "dblp"
    elif oa_author.get("homepage_url"):
        homepage_url = oa_author["homepage_url"]
        homepage_source = "openalex"

    # --- 5. Fetch homepage (best-effort) ---
    homepage_data = {"position": None, "email": None, "lab_name": None,
                     "lab_url": None, "accepting_signal": None, "error": None}
    if homepage_url:
        hp_cache_key = f"homepage:{homepage_url}"
        cached_hp = _cache.get(hp_cache_key, "homepage")
        if cached_hp:
            homepage_data = cached_hp
        else:
            hp_svc = HomepageService()
            homepage_data = await hp_svc.fetch(homepage_url)
            if not homepage_data.get("error"):
                _cache.set(hp_cache_key, homepage_data, "homepage",
                           ttl_seconds=Cache.HOMEPAGE_TTL)

    # --- 6. Institution tier ---
    inst_name = oa_author.get("institution") or ""
    country_code = oa_author.get("country_code")
    tier_info = _institution_clf.classify(inst_name, country_code)

    # --- 7. Seniority (DBLP first pub year as proxy) ---
    first_pub_year = dblp_record.get("first_pub_year") if dblp_record else None
    seniority = compute_seniority(first_pub_year) if first_pub_year else None
    seniority_source = "dblp_estimate" if first_pub_year else "unknown"

    # --- 8. is_pi heuristic ---
    works_count = oa_author.get("works_count", 0) or 0
    inst_type = oa_author.get("institution_type", "")
    position_val = homepage_data.get("position")
    if position_val and "professor" in position_val.lower():
        is_pi_val, is_pi_conf = True, "high"
    elif works_count > 50 and inst_type == "education":
        is_pi_val, is_pi_conf = True, "medium"
    elif works_count > 20:
        is_pi_val, is_pi_conf = True, "low"
    else:
        is_pi_val, is_pi_conf = None, "unknown"

    # --- 9. Assemble result ---
    dblp_pid = dblp_record["pid"] if dblp_record else None
    result = {
        "openalex_id": openalex_id,
        "dblp_pid": dblp_pid,
        "name": oa_author.get("name", ""),
        "institution": _sourced(
            inst_name,
            ["openalex"] + (["homepage"] if homepage_data.get("position") else []),
            "high" if inst_name else "unknown",
        ),
        "country_code": country_code,
        "institution_tier": tier_info.get("tier"),
        "position": _sourced(
            position_val,
            ["homepage"] if position_val else [],
            "medium" if position_val else "unknown",
        ),
        "is_pi": _sourced(is_pi_val, ["homepage" if position_val else "openalex_heuristic"],
                          is_pi_conf),
        "h_index": _sourced(oa_author.get("h_index"), ["openalex"], "high"),
        "citation_count": _sourced(oa_author.get("citation_count"), ["openalex"], "high"),
        "works_count": oa_author.get("works_count"),
        "papers_last_3_years": oa_author.get("papers_last_3_years"),
        "first_pub_year": first_pub_year,
        "seniority": seniority,
        "seniority_source": seniority_source,
        "homepage_url": homepage_url,
        "homepage_source": homepage_source,
        "homepage_search_query": (
            f"{oa_author.get('name', '')} {inst_name} homepage"
            if not homepage_url else None
        ),
        "concepts": oa_author.get("concepts", []),
        "recent_papers": [p.model_dump() for p in recent_papers],
        "email": homepage_data.get("email"),
        "lab_name": homepage_data.get("lab_name"),
        "lab_url": homepage_data.get("lab_url"),
        "accepting_students_signal": homepage_data.get("accepting_signal"),
    }

    _cache.set(openalex_id, result, "professor_details", ttl_seconds=Cache.PROFESSOR_TTL)
    return result
```

- [ ] **Step 4: 运行测试，确认通过**

```powershell
pytest tests/test_tools_details.py -v
```

预期：1 test PASSED

- [ ] **Step 5: Commit**

```powershell
git add src/professor_fit_mcp/tools/details.py tests/test_tools_details.py
git commit -m "feat: add get_professor_details tool (multi-source merge with sourced fields)"
```

---

## Task 11: rank_fit 工具

**Files:**
- Create: `src/professor_fit_mcp/tools/ranking.py`
- Test: `tests/test_tools_ranking.py`

确定性粗筛（整词匹配 concepts + 论文文本）+ 打包精排材料供 client LLM。

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_tools_ranking.py
import pytest
from professor_fit_mcp.tools.ranking import rank_fit_impl, compute_professor_relevance

_PROF_BLOCKCHAIN = {
    "openalex_id": "A1",
    "name": "Alice Smith",
    "institution": "MIT",
    "country_code": "US",
    "institution_tier": "R1",
    "h_index": {"value": 65, "sources": ["openalex"], "confidence": "high"},
    "citation_count": {"value": 18000, "sources": ["openalex"], "confidence": "high"},
    "concepts": ["Blockchain", "Consensus Protocols", "Distributed Systems"],
    "recent_papers": [
        {"title": "MEV in Blockchain", "year": 2024, "abstract": "We study MEV on blockchain", "source": "openalex"},
        {"title": "Fair Ordering", "year": 2023, "abstract": "blockchain consensus fairness", "source": "openalex"},
    ],
    "homepage_url": "https://alice.mit.edu",
}

_PROF_UNRELATED = {
    "openalex_id": "B2",
    "name": "Bob Jones",
    "institution": "Harvard",
    "country_code": "US",
    "institution_tier": "R1",
    "h_index": {"value": 90, "sources": ["openalex"], "confidence": "high"},
    "citation_count": {"value": 50000, "sources": ["openalex"], "confidence": "high"},
    "concepts": ["Immunology", "Genomics"],
    "recent_papers": [
        {"title": "CRISPR therapy", "year": 2024, "abstract": "gene editing study", "source": "openalex"},
    ],
    "homepage_url": None,
}


def test_compute_relevance_high():
    score = compute_professor_relevance(
        professor=_PROF_BLOCKCHAIN,
        keywords=["blockchain", "consensus", "MEV"],
    )
    assert score > 0.8


def test_compute_relevance_low():
    score = compute_professor_relevance(
        professor=_PROF_UNRELATED,
        keywords=["blockchain", "consensus", "MEV"],
    )
    assert score == 0.0


@pytest.mark.asyncio
async def test_rank_fit_sorts_by_relevance():
    result = await rank_fit_impl(
        user_interests={"keywords": ["blockchain", "consensus", "MEV"]},
        professors=[_PROF_UNRELATED, _PROF_BLOCKCHAIN],
    )
    profs = result["ranked_professors"]
    assert profs[0]["professor"]["openalex_id"] == "A1"
    assert profs[0]["relevance_signal"] > profs[1]["relevance_signal"]


@pytest.mark.asyncio
async def test_rank_fit_filter_min_citation():
    result = await rank_fit_impl(
        user_interests={"keywords": ["blockchain"]},
        professors=[_PROF_BLOCKCHAIN],
        filters={"min_citation": 999999},
    )
    assert len(result["ranked_professors"]) == 0


@pytest.mark.asyncio
async def test_rank_fit_returns_fit_materials():
    result = await rank_fit_impl(
        user_interests={"keywords": ["blockchain"], "description": "I study blockchain"},
        professors=[_PROF_BLOCKCHAIN],
    )
    prof_entry = result["ranked_professors"][0]
    assert "fit_materials" in prof_entry
    assert "concepts" in prof_entry["fit_materials"]
    assert "recent_papers_summary" in prof_entry["fit_materials"]
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_tools_ranking.py -v
```

- [ ] **Step 3: 实现 `tools/ranking.py`**

```python
# src/professor_fit_mcp/tools/ranking.py
from typing import Optional
from ..utils.text_processing import compute_keyword_overlap

_PRESETS = {
    "blockchain_security": ["blockchain", "consensus", "MEV", "DeFi", "systems security",
                             "distributed systems", "cryptography", "smart contracts"],
    "ai_ml": ["machine learning", "deep learning", "NLP", "computer vision", "LLM",
               "foundation model", "reinforcement learning"],
    "systems": ["operating systems", "distributed systems", "cloud", "storage",
                 "networking", "databases", "architecture"],
    "security": ["security", "privacy", "cryptography", "adversarial", "vulnerability",
                  "malware", "authentication"],
}


def compute_professor_relevance(professor: dict, keywords: list[str]) -> float:
    """
    Whole-word keyword overlap against concepts + recent paper titles + abstracts.
    Returns 0.0-1.0.
    """
    if not keywords:
        return 0.0

    parts = list(professor.get("concepts") or [])
    for paper in professor.get("recent_papers") or []:
        if isinstance(paper, dict):
            parts.append(paper.get("title") or "")
            parts.append(paper.get("abstract") or "")

    corpus = " ".join(parts)
    return compute_keyword_overlap(keywords, corpus)


def _extract_keywords(user_interests: dict) -> list[str]:
    """Resolve user_interests dict to a flat list of keywords."""
    if "preset" in user_interests:
        preset_kws = _PRESETS.get(user_interests["preset"], [])
        extra = user_interests.get("keywords", [])
        return preset_kws + extra

    return user_interests.get("keywords", [])


def _apply_filters(professor: dict, filters: dict) -> bool:
    """Return True if professor passes all filters."""
    citation = (professor.get("citation_count") or {}).get("value") or 0
    if filters.get("min_citation") and citation < filters["min_citation"]:
        return False

    if filters.get("regions"):
        allowed = {r.upper() for r in filters["regions"]}
        if professor.get("country_code", "").upper() not in allowed:
            return False

    if filters.get("institution_tier"):
        allowed_tiers = {t.upper() for t in filters["institution_tier"]}
        tier = (professor.get("institution_tier") or "").upper()
        if tier not in allowed_tiers:
            return False

    return True


async def rank_fit_impl(
    user_interests: dict,
    professors: list[dict],
    filters: Optional[dict] = None,
    sort_by: str = "relevance_signal",
) -> dict:
    """
    Deterministic coarse ranking + packaging materials for client LLM fit judgment.

    The docstring below is the rubric the client LLM should use to produce
    fit_level / match_reasons / potential_concerns / email_advice:

    RUBRIC FOR CLIENT LLM:
    - HIGH fit: professor's recent papers directly address user's core keywords;
      multiple concept overlaps; active in the exact subfield.
    - MEDIUM fit: related area, some overlap but not the primary focus.
    - LOW fit: tangentially related or older work in the area.
    - Produce: fit_level (HIGH|MEDIUM|LOW), match_reasons (list), potential_concerns (list),
      email_advice (1-2 sentences on what to mention in cold email).
    """
    keywords = _extract_keywords(user_interests)
    filters = filters or {}

    ranked = []
    for prof in professors:
        if not _apply_filters(prof, filters):
            continue

        score = compute_professor_relevance(prof, keywords)

        # Build fit materials for client LLM
        papers_summary = [
            {
                "title": p.get("title") if isinstance(p, dict) else p.title,
                "year": p.get("year") if isinstance(p, dict) else p.year,
                "abstract": (p.get("abstract") if isinstance(p, dict) else p.abstract) or "",
            }
            for p in (prof.get("recent_papers") or [])
        ]

        ranked.append({
            "professor": prof,
            "relevance_signal": round(score, 3),
            "fit_materials": {
                "user_interests": user_interests,
                "concepts": prof.get("concepts", []),
                "recent_papers_summary": papers_summary,
                "keywords_used": keywords,
            },
        })

    # Sort
    reverse = True
    if sort_by == "citation":
        ranked.sort(
            key=lambda x: (x["professor"].get("citation_count") or {}).get("value") or 0,
            reverse=True,
        )
    else:
        ranked.sort(key=lambda x: x["relevance_signal"], reverse=True)

    return {
        "ranked_professors": ranked,
        "total": len(ranked),
        "keywords_used": keywords,
        "sort_by": sort_by,
    }
```

- [ ] **Step 4: 运行测试，确认全部通过**

```powershell
pytest tests/test_tools_ranking.py -v
```

预期：5 tests PASSED

- [ ] **Step 5: Commit**

```powershell
git add src/professor_fit_mcp/tools/ranking.py tests/test_tools_ranking.py
git commit -m "feat: add rank_fit tool (whole-word relevance scoring + fit materials for client LLM)"
```

---

## Task 12: export_table 工具

**Files:**
- Create: `src/professor_fit_mcp/exporters/markdown.py`
- Create: `src/professor_fit_mcp/exporters/csv_export.py`
- Create: `src/professor_fit_mcp/exporters/json_export.py`
- Create: `src/professor_fit_mcp/tools/export.py`
- Test: `tests/test_tools_export.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_tools_export.py
import csv, io, json
import pytest
from professor_fit_mcp.tools.export import export_table_impl

_RANKED = [
    {
        "professor": {
            "openalex_id": "A1",
            "name": "Alice Smith",
            "institution": "MIT",
            "country_code": "US",
            "institution_tier": "R1",
            "h_index": {"value": 65, "sources": ["openalex"], "confidence": "high"},
            "citation_count": {"value": 18000, "sources": ["openalex"], "confidence": "high"},
            "homepage_url": "https://alice.mit.edu",
            "seniority": "mid-career",
            "accepting_students_signal": None,
        },
        "relevance_signal": 0.9,
    }
]


def test_export_markdown_contains_name():
    result = export_table_impl(professors=_RANKED, format="markdown")
    assert "Alice Smith" in result["content"]
    assert "|" in result["content"]  # table format


def test_export_csv_parseable():
    result = export_table_impl(professors=_RANKED, format="csv")
    reader = csv.DictReader(io.StringIO(result["content"]))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice Smith"
    assert rows[0]["relevance_signal"] == "0.9"


def test_export_json_parseable():
    result = export_table_impl(professors=_RANKED, format="json")
    data = json.loads(result["content"])
    assert len(data) == 1
    assert data[0]["name"] == "Alice Smith"


def test_export_with_summary():
    result = export_table_impl(professors=_RANKED, format="markdown", include_summary=True)
    assert "Total" in result["content"] or "1" in result["content"]


def test_export_to_file(tmp_path):
    out = str(tmp_path / "output.md")
    result = export_table_impl(professors=_RANKED, format="markdown", output_path=out)
    import os
    assert os.path.exists(out)
    assert result["saved_to"] == out
```

- [ ] **Step 2: 运行测试，确认失败**

```powershell
pytest tests/test_tools_export.py -v
```

- [ ] **Step 3: 实现 exporters**

```python
# src/professor_fit_mcp/exporters/markdown.py
from tabulate import tabulate

_COLS = ["rank", "name", "institution", "country_code", "institution_tier",
         "h_index", "citation_count", "seniority", "relevance_signal", "homepage_url"]

def to_markdown(ranked: list[dict], include_summary: bool = False) -> str:
    rows = []
    for i, entry in enumerate(ranked, 1):
        prof = entry.get("professor", {})
        rows.append([
            i,
            prof.get("name", ""),
            prof.get("institution", ""),
            prof.get("country_code", ""),
            prof.get("institution_tier") or "-",
            (prof.get("h_index") or {}).get("value", "-"),
            (prof.get("citation_count") or {}).get("value", "-"),
            prof.get("seniority") or "-",
            entry.get("relevance_signal", "-"),
            prof.get("homepage_url") or "-",
        ])
    headers = ["#", "Name", "Institution", "Country", "Tier",
               "h-index", "Citations", "Seniority", "Relevance", "Homepage"]
    table = tabulate(rows, headers=headers, tablefmt="pipe")
    summary = f"\n\n**Total:** {len(ranked)} professors" if include_summary else ""
    return f"# Professor Fit Results\n\n{table}{summary}\n"
```

```python
# src/professor_fit_mcp/exporters/csv_export.py
import csv, io

def to_csv(ranked: list[dict]) -> str:
    fieldnames = ["rank", "name", "institution", "country_code", "institution_tier",
                  "h_index", "citation_count", "seniority", "relevance_signal", "homepage_url"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for i, entry in enumerate(ranked, 1):
        prof = entry.get("professor", {})
        writer.writerow({
            "rank": i,
            "name": prof.get("name", ""),
            "institution": prof.get("institution", ""),
            "country_code": prof.get("country_code", ""),
            "institution_tier": prof.get("institution_tier") or "",
            "h_index": (prof.get("h_index") or {}).get("value", ""),
            "citation_count": (prof.get("citation_count") or {}).get("value", ""),
            "seniority": prof.get("seniority") or "",
            "relevance_signal": entry.get("relevance_signal", ""),
            "homepage_url": prof.get("homepage_url") or "",
        })
    return output.getvalue()
```

```python
# src/professor_fit_mcp/exporters/json_export.py
import json

def to_json(ranked: list[dict]) -> str:
    output = []
    for i, entry in enumerate(ranked, 1):
        prof = entry.get("professor", {})
        output.append({
            "rank": i,
            "name": prof.get("name", ""),
            "institution": prof.get("institution", ""),
            "country_code": prof.get("country_code", ""),
            "institution_tier": prof.get("institution_tier"),
            "h_index": (prof.get("h_index") or {}).get("value"),
            "citation_count": (prof.get("citation_count") or {}).get("value"),
            "seniority": prof.get("seniority"),
            "relevance_signal": entry.get("relevance_signal"),
            "homepage_url": prof.get("homepage_url"),
            "concepts": prof.get("concepts", []),
            "accepting_students_signal": prof.get("accepting_students_signal"),
        })
    return json.dumps(output, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: 实现 `tools/export.py`**

```python
# src/professor_fit_mcp/tools/export.py
from pathlib import Path
from typing import Optional
from ..exporters.markdown import to_markdown
from ..exporters.csv_export import to_csv
from ..exporters.json_export import to_json


def export_table_impl(
    professors: list[dict],
    format: str = "markdown",
    include_summary: bool = False,
    output_path: Optional[str] = None,
) -> dict:
    """Format ranked professors as markdown/csv/json. Optionally save to file."""
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
```

- [ ] **Step 5: 运行测试，确认全部通过**

```powershell
pytest tests/test_tools_export.py -v
```

预期：5 tests PASSED

- [ ] **Step 6: Commit**

```powershell
git add src/professor_fit_mcp/exporters/ src/professor_fit_mcp/tools/export.py tests/test_tools_export.py
git commit -m "feat: add export_table tool with markdown/csv/json exporters"
```

---

## Task 13: MCP Server 入口 + 烟雾测试

**Files:**
- Create: `src/professor_fit_mcp/server.py`
- Create: `README.md`

- [ ] **Step 1: 实现 `server.py`**

```python
# src/professor_fit_mcp/server.py
"""
Professor Fit MCP Server

Helps PhD applicants find matching professors.
Input: research interests (keywords / paper URL)
Output: structured professor data with provenance for client LLM fit judgment.

CLIENT LLM RUBRIC (for rank_fit results):
- HIGH fit: professor's recent papers directly address user's core keywords; multiple concept overlaps.
- MEDIUM fit: related area with some overlap but not primary focus.
- LOW fit: tangential or older work in the area.
For each professor, produce: fit_level, match_reasons (list), potential_concerns (list), email_advice.
"""
from mcp.server.fastmcp import FastMCP
from typing import Optional

from .tools.search import search_professors_impl
from .tools.details import get_professor_details_impl
from .tools.ranking import rank_fit_impl
from .tools.export import export_table_impl

mcp = FastMCP("professor-fit")


@mcp.tool()
async def search_professors(
    keywords: list[str],
    paper_url: Optional[str] = None,
    regions: Optional[list[str]] = None,
    university_filter: Optional[list[str]] = None,
    institution_tier: Optional[list[str]] = None,
    limit: int = 20,
) -> dict:
    """
    Search for professors matching research interests (coarse filter).

    Args:
        keywords: Research interest keywords, e.g. ["blockchain", "consensus", "MEV"]
        paper_url: Optional arXiv/DOI URL to extract keywords from
        regions: Country/region codes to filter by, e.g. ["US", "UK", "CN"].
                 Supported: US, UK/GB, CN, JP, KR, DE, CA, AU, SG, HK, ASIA, ALL
        university_filter: Specific university names to include
        institution_tier: Filter by tier, e.g. ["R1", "Russell", "985"]
        limit: Max number of results (default 20)

    Returns:
        dict with "professors" list and "total_found". Each professor includes
        openalex_id, name, institution, country_code, institution_tier, h_index,
        citation_count, concepts, homepage_url (or homepage_search_query for client fallback).
    """
    return await search_professors_impl(
        keywords=keywords,
        paper_url=paper_url,
        regions=regions,
        university_filter=university_filter,
        institution_tier=institution_tier,
        limit=limit,
    )


@mcp.tool()
async def get_professor_details(
    professor_id: Optional[str] = None,
    name: Optional[str] = None,
    university: Optional[str] = None,
) -> dict:
    """
    Get detailed multi-source profile for a professor.

    Fetches from OpenAlex (metrics, concepts, recent papers) + DBLP (homepage URL,
    first publication year) + homepage (position, email, lab, accepting students signal).
    All key fields include source and confidence metadata.

    Args:
        professor_id: OpenAlex author ID (preferred), e.g. "A5023888391"
        name: Professor's name (used if professor_id not provided)
        university: University name to disambiguate when searching by name

    Returns:
        Full professor profile with sourced fields (value/sources/confidence),
        recent papers (last 3 years), seniority estimate, and accepting_students_signal.
        If homepage_url is null, homepage_search_query is provided for client web search.
    """
    return await get_professor_details_impl(
        professor_id=professor_id,
        name=name,
        university=university,
    )


@mcp.tool()
async def rank_fit(
    user_interests: dict,
    professors: list[dict],
    filters: Optional[dict] = None,
    sort_by: str = "relevance_signal",
) -> dict:
    """
    Rank professors by keyword overlap and package materials for client LLM fit judgment.

    SERVER SIDE: Deterministic whole-word keyword matching against concepts + paper titles/abstracts.
    CLIENT SIDE: Use the fit_materials in each result to produce fit_level, match_reasons,
    potential_concerns, and email_advice.

    Args:
        user_interests: Dict with one of:
          - {"keywords": ["blockchain", "MEV"]}
          - {"preset": "blockchain_security"}  (built-in presets: blockchain_security, ai_ml, systems, security)
          - {"keywords": [...], "description": "free text", "paper_urls": [...]}
        professors: List from search_professors or get_professor_details
        filters: Optional filters:
          - min_citation: int
          - regions: list[str]
          - institution_tier: list[str]
        sort_by: "relevance_signal" (default) | "citation"

    Returns:
        ranked_professors list, each with:
          - professor: the professor dict
          - relevance_signal: float 0.0-1.0 (keyword overlap score)
          - fit_materials: {user_interests, concepts, recent_papers_summary, keywords_used}
            → pass this to client LLM to generate final fit assessment
    """
    return await rank_fit_impl(
        user_interests=user_interests,
        professors=professors,
        filters=filters,
        sort_by=sort_by,
    )


@mcp.tool()
async def export_table(
    professors: list[dict],
    format: str = "markdown",
    include_summary: bool = True,
    output_path: Optional[str] = None,
) -> dict:
    """
    Export ranked professors as a formatted table.

    Args:
        professors: ranked_professors list from rank_fit
        format: "markdown" (default) | "csv" | "json"
        include_summary: Include count summary (default True)
        output_path: Optional file path to save output

    Returns:
        dict with "content" (string), "format", and "saved_to" (path if saved).
    """
    return export_table_impl(
        professors=professors,
        format=format,
        include_summary=include_summary,
        output_path=output_path,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 创建 README.md**

```markdown
# Professor Fit MCP

帮 PhD 申请者匹配教授的 MCP server。

## 安装

```bash
pip install -e .
```

## Claude Desktop 配置

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "professor-fit": {
      "command": "python",
      "args": ["-m", "professor_fit_mcp.server"],
      "env": {
        "OPENALEX_EMAIL": "your@email.com"
      }
    }
  }
}
```

## 使用示例

```
搜 blockchain security 教授，限美国 R1 院校：

1. search_professors(keywords=["blockchain","consensus","MEV"], regions=["US"], institution_tier=["R1"])
2. get_professor_details(professor_id="A123...")  # 获取详情
3. rank_fit(user_interests={"preset":"blockchain_security"}, professors=[...])
4. export_table(professors=[...], format="markdown")
```

## 工具

| 工具 | 功能 |
|------|------|
| `search_professors` | 按关键词粗筛候选教授（OpenAlex） |
| `get_professor_details` | 多源详情（OpenAlex+DBLP+主页） |
| `rank_fit` | 整词匹配粗排 + 打包精排材料 |
| `export_table` | 输出 markdown/csv/json |
```

- [ ] **Step 3: 烟雾测试——确认 server 可以启动**

```powershell
python -c "from professor_fit_mcp.server import mcp; print('Server OK:', mcp.name)"
```

预期输出：`Server OK: professor-fit`

- [ ] **Step 4: 运行全部测试**

```powershell
pytest tests/ -v --tb=short
```

预期：全部通过

- [ ] **Step 5: 最终 Commit**

```powershell
git add src/professor_fit_mcp/server.py README.md
git commit -m "feat: wire MCP server with 4 tools (search/details/rank_fit/export_table)"
git tag v0.1.0
```

---

## 自检：Spec 覆盖确认

| Spec 要求 | 对应 Task | 状态 |
|-----------|-----------|------|
| 4 个 MCP 工具 | Task 9/10/11/12/13 | ✅ |
| OpenAlex 主干（h-index/citations/concepts/消歧） | Task 6 | ✅ |
| DBLP homepage URL + first_pub_year | Task 7 | ✅ |
| 主页 best-effort（职称/email/lab/招生） | Task 8 | ✅ |
| 分层主页发现（DBLP→OpenAlex→client search_query） | Task 10 | ✅ |
| SourcedField（value/sources/confidence） | Task 2 | ✅ |
| SQLite 缓存（教授7天/主页1天） | Task 3 | ✅ |
| 整词匹配（修掉子串误判） | Task 4 | ✅ |
| 院校分级清单（R1/985/Russell/Go8…） | Task 5 | ✅ |
| seniority 估算（DBLP首发年代理） | Task 10 | ✅ |
| accepting_students 招生信号（best-effort） | Task 8 | ✅ |
| rank_fit docstring 内置 rubric 给 client LLM | Task 11/13 | ✅ |
| markdown + csv + json 导出 | Task 12 | ✅ |
| 零 key 默认可用 | 全程无强制 key | ✅ |
| 诚实数据（拿不到标 unknown/null） | Task 10 | ✅ |

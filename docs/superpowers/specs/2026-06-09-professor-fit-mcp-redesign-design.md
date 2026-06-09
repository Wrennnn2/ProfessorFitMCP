# Professor Fit MCP — 重构架构设计（Spec）

**日期：** 2026-06-09
**状态：** 已确认，待生成实施计划
**取代：** `docs/architecture.md`（原始设计，部分假设不可行，本 spec 为其修订版）

---

## 1. 目标与定位

帮 PhD 申请者匹配教授：输入研究兴趣（关键词 / 论文链接），输出可排序、带溯源与置信度的「教授匹配度」材料，供 client LLM 生成最终 fit 表格。

**核心定位：轻服务器（Thin Server）。**
- Server 只做「LLM 做不到的事」：联网取数据、跨源整合、结构化输出。
- 语义 fit 判断（HIGH/MEDIUM/LOW、match_reasons、套磁建议）交给调用方的 client LLM（Claude / Cursor 等）完成。
- 主要使用场景：运行在具备强 LLM 能力的 MCP client 内。

---

## 2. 设计总原则

1. **轻服务器**：取数据 + 结构化在 server；语义判断在 client。
2. **OpenAlex 为主干**：免费、无需 key、自带作者消歧与 h-index。
3. **多源交叉验证**：OpenAlex + DBLP + arXiv + 主页，互相印证，记录来源与置信度。
4. **诚实数据原则**：每个关键字段带 `source` 与 `confidence`；拿不到就标 `unknown`，绝不编造。
5. **零 key 默认可用**：核心路径不需要任何 API key；进阶能力作为可选项。
6. **YAGNI**：先砍掉不可靠 / 低价值的字段与格式，架构预留演进口子。

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        MCP Client                            │
│             (Claude / Cursor) — 负责语义 fit 判断             │
│             并提供 web search 兜底（主页发现第 3 层）          │
└─────────────────────────────────────────────────────────────┘
                              │  MCP 协议
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Professor Fit MCP Server                    │
│                                                             │
│  Tool Layer                                                 │
│   search_professors · get_professor_details                 │
│   rank_fit · export_table                                   │
│                                                             │
│  Service Layer                                              │
│   openalex   — 主干：指标/机构/concepts/消歧                 │
│   dblp       — CS 发表记录/venue/合作者/主页URL              │
│   arxiv      — 近期论文摘要（fit 材料，近 3 年）               │
│   homepage   — best-effort 抓取：职称/email/lab              │
│   resolver   — 跨源身份消歧与字段级交叉验证（非 Crossref API）│
│   institution— 院校分级清单（R1/985/Russell…）              │
│   cache      — 本地缓存 + 限流/并发控制                       │
│                                                             │
│  论文搜索：import paper-search-mcp 作为库（arxiv/dblp/openalex）│
└─────────────────────────────────────────────────────────────┘
```

**与 paper-search-mcp 的集成方式：** 直接 `import` 其内部 platform 模块（已验证可行）：`from paper_search_mcp.academic_platforms.arxiv import ArxivSearch`、`from paper_search_mcp.academic_platforms.dblp import DBLPSearch` 等，**不**以子进程方式起 MCP client。DBLP 和 arXiv 的抓取逻辑因此几乎是现成的，无需从头实现。

---

## 4. 数据源策略

### 4.1 多源分工

| 数据源 | 角色 | 提供 | key |
|--------|------|------|-----|
| **OpenAlex** | 主干 | h-index(`summary_stats`)、引用、机构(country/type)、concepts/topics、counts_by_year（活跃度）、作者消歧、论文 | 否 |
| **DBLP** | CS 重器 | 发表记录、顶会 venue、合作者图、**person record 的 homepage URL** | 否 |
| **arXiv** | 摘要源 | 近期论文标题/摘要（fit 判断关键材料） | 否 |
| **个人主页** | best-effort | 职称（Assistant/Associate/Full Professor）、email、lab_url | 否 |
| Google Scholar | 可选增强（默认关闭） | h-index/引用补充 | 否（爬取） |

### 4.2 交叉验证机制

**身份确认（消歧）：** 跨 OpenAlex / DBLP 用「姓名 + 机构 + 合作者重叠」匹配。
- 三者一致 → 置信 high；冲突 → 标记 `conflict`，保留多值不强行二选一。

**字段级交叉验证：** 每个字段记录「哪些源提供了它、是否一致」。
- 例：机构 OpenAlex=Stanford 且 主页=Stanford → confidence=high。
- 例：研究方向 = OpenAlex concepts ∩ DBLP venues ∩ arXiv 摘要，互相印证。

### 4.3 缓存与限流

- 本地缓存：使用 **SQLite**（单文件、并发安全），按 `openalex_author_id` 为 key，TTL = **7 天**（教授数据变化慢；主页内容 TTL = 1 天）。
- async httpx + 信号量限并发 + 超时 + 指数退避重试。
- `cache.py` 必须真正实现（原设计为空壳）。

---

## 5. 教授识别层（化解原设计致命问题）

诚实前提：「是否教授」「phd_year」「是否招生」无法从 API 精确得到。改用**可靠代理 + 置信度**：

| 字段 | 方案 | 主要来源 |
|------|------|----------|
| 是否教授 / PI | 主页职称为**直接证据**（"Assistant/Associate/Full Professor"）；辅以 DBLP 发表跨度、OpenAlex 启发式（works_count、常任末位/通讯作者、机构 type=education）→ 输出「PI 可能性」分数与 confidence | 主页 > DBLP > OpenAlex |
| seniority / phd_year | **DBLP 首篇发表年 + 发表跨度**为主代理（学术年龄）；主页 "Joined in 20XX" 佐证；标注为估算，非精确 | DBLP / 主页 |
| accepting_students | **不承诺结构化字段**；best-effort 抓取主页文本，若检测到招生关键词（"looking for students"、"recruiting"、"开放招生"等），返回含原文摘录的信号对象（signal/snippet/confidence=low）；找不到则返回 null；同时提供 homepage_url 让用户自行核实 | 主页（弱） |
| 同名消歧 | 以 **OpenAlex author_id 为主键**（已做消歧），跨源仅做验证不强行合并 | OpenAlex |

---

## 6. 主页发现策略（分层 + client 兜底，零 key）

```
找 homepage_url，命中即停：
1. DBLP person record 的 url 字段            ← server，免费可靠，CS 覆盖高
2. OpenAlex 作者 homepage（若有）             ← server，免费
3. 仍无 → server 返回 homepage_url=null
        + 附 search_query（如 "Percy Liang Stanford homepage"）
        → 交 client LLM 自带 web search 补全   ← client 兜底
4. client 也找不到 → 标记 unknown
```

Server 端零搜索依赖、零 key、不碰反爬。找到主页后再 best-effort 抓取职称 / email / lab_url。

---

## 7. fit 精排层

```
Server 端（确定性、免费、快）= 粗筛信号
  - OpenAlex concepts/topics 与用户关键词重叠打分
  - + 近期论文文本匹配（用整词匹配，修掉原设计的子串误判 bug）
  - 输出 relevance_signal（可排序，但非最终 fit）

Client LLM 端 = 最终判断
  - server 返回结构化材料：用户兴趣 + 每位教授 topics + 近 3 年论文标题/摘要
  - rank_fit 工具的 docstring 内置 rubric，指导 client 产出
    fit_level / match_reasons / potential_concerns / email_advice
```

**注意：** 原设计 6.1 节的复杂混合加权（embedding + 自带 LLM）不在本版实现；语义部分由 client 承担。`llm_service.py` 及 openai/anthropic/sentence-transformers 不作为必需依赖。

---

## 8. MCP Tools 设计（保留 4 个）

### 8.1 `search_professors`
根据研究兴趣粗筛候选教授。
- 输入：`keywords`(必填)、`paper_url`(可选)、`regions`、`university_filter`、`institution_tier`、`limit`。
- 输出：候选教授列表，含 OpenAlex 基础数据（name、institution、metrics、concepts、recent_papers 摘要）、`homepage_url`（或 null + search_query）、字段级 `source`/`confidence`。

### 8.2 `get_professor_details`
丰富单个教授信息（多源交叉验证 + best-effort 抓主页）。
- 输入：`professor_id`（OpenAlex id）或 `name` + `university`。
- 输出：带溯源结构的详情字段，示例：
```python
"institution": {"value": "Stanford University", "sources": ["openalex","homepage"], "confidence": "high"},
"position":    {"value": "Associate Professor", "sources": ["homepage"], "confidence": "medium"},
"homepage_url":{"value": "https://...", "source": "dblp"},
"seniority":   {"value": "mid-career", "source": "dblp_estimate", "confidence": "medium"},
"h_index":     {"value": 85, "source": "openalex", "confidence": "high"},
```

### 8.3 `rank_fit`
重定义为「确定性粗筛 + 打包精排材料」。
- 输入：`user_interests`（keywords / preset / description / paper_urls）、`professors`、`filters`（regions/tier/min_citation 等）、`sort_by`。
- 输出：附 `relevance_signal` 的排序列表 + 供 client 判断的结构化材料；最终 fit_level/reasons 由 client 依 docstring rubric 生成。

### 8.4 `export_table`
格式化输出。
- 格式：`markdown` | `csv` | `json`（**不含 xlsx**）。
- 选项：列选择、`include_summary`、`locale`(zh/en)、`output_path`(可选)。

---

## 9. 院校数据层（瘦身）

- 国家 / 机构 type 直接取 **OpenAlex**（已有 country_code、institution type）。
- 只内置「有限且明确的分级清单」：US R1(Carnegie)、CN 985/211/双一流、UK Russell、AU Go8、CA U15、DE TU9、JP 旧帝大、KR SKY 等。
- QS / CS Ranking 精确排名数字 → best-effort/可选，**初版不承诺全覆盖**。

---

## 10. 项目结构

```
professor-fit-mcp/
├── src/professor_fit_mcp/
│   ├── server.py                # MCP Server 入口；工具 docstring 内置 fit rubric
│   ├── tools/
│   │   ├── search.py            # search_professors
│   │   ├── details.py           # get_professor_details
│   │   ├── ranking.py           # rank_fit（粗筛+打包材料）
│   │   └── export.py            # export_table
│   ├── services/
│   │   ├── paper_search.py      # import paper-search-mcp 的封装
│   │   ├── openalex.py          # 主干
│   │   ├── dblp.py              # 发表记录/venue/合作者/主页URL
│   │   ├── arxiv.py             # 摘要
│   │   ├── homepage.py          # best-effort 主页抓取
│   │   ├── resolver.py          # 身份消歧 + 字段级交叉验证
│   │   └── institution.py       # 院校分级清单
│   ├── models/
│   │   ├── professor.py         # 含 source/confidence 的字段结构
│   │   ├── paper.py
│   │   └── fit_result.py
│   ├── exporters/
│   │   ├── markdown.py
│   │   ├── csv_export.py
│   │   └── json_export.py
│   └── utils/
│       ├── text_processing.py   # 整词匹配等
│       └── cache.py             # 真正实现：缓存+限流+并发
├── data/institutions/           # 各国分级清单 JSON
├── tests/
├── docs/
├── pyproject.toml
├── README.md
└── .env.example
```

---

## 11. 依赖

```toml
[project]
dependencies = [
    "mcp>=1.0.0",
    "paper-search-mcp>=0.3.0",   # arXiv/DBLP/OpenAlex 等
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",    # 主页解析
    "pydantic>=2.0.0",
    "tabulate>=0.9.0",           # markdown 表格
]

[project.optional-dependencies]
ranking = ["scikit-learn>=1.3.0"]      # 可选 TF-IDF 粗筛
scholar = ["scholarly>=1.7.0"]         # 可选 Google Scholar 增强
```

**相对原设计移除的必需依赖：** `scholarly`、`openai`/`anthropic`、`openpyxl`、`sentence-transformers`。

---

## 12. 参考项目

以下开源项目已调研，不作为依赖引入，但实施时可作代码参考：

| 项目 | 参考价值 | 使用方式 |
|------|----------|----------|
| [alisoroushmd/academic-research-mcp](https://github.com/alisoroushmd/academic-research-mcp) | 已实现 `search_authors` / `get_author` / `get_author_works`，跨 OpenAlex + Semantic Scholar + ORCID；包含作者消歧、pagination、限流处理逻辑 | 实施 `openalex.py` / `resolver.py` 时对照其源码，学习 OpenAlex Authors API 调用方式和跨源消歧模式 |
| [openags/paper-search-mcp](https://github.com/openags/paper-search-mcp) | 已实现 arXiv / DBLP / OpenAlex 等 20+ 数据源的 Python 抓取模块 | **直接作为依赖**（`pip install paper-search-mcp`），import 其 `academic_platforms` 子模块 |

**不引入的原因（academic-research-mcp）：** 它本身也是 MCP server；从我们的 MCP server 里调用另一个 MCP server 会造成嵌套 client/server 复杂度。只借鉴其逻辑，不引入依赖。

**已排除的项目：**
- Scholar-MCP：核心优势依赖 Scopus 付费 API key，与「零 key 默认可用」原则冲突，无增量价值。
- ARCANE / semantic-scholar-mcp / Google-Scholar-MCP-Server：定位为通用论文搜索，与本项目无重叠。

---

## 13. 不在本版范围（YAGNI / 后续）

- 自带 LLM 精排（server 端 embedding / LLM 调用）
- xlsx 导出
- QS/CS 精确排名全覆盖
- deadline 提醒、套磁邮件草稿生成、搜索历史、教授对比
- 结构化的 `accepting_students` 承诺

---

## 14. 关键风险与缓解

| 风险 | 缓解 |
|------|------|
| 主页格式千差万别，抓取不稳 | best-effort + confidence；失败标 unknown，不阻塞主流程 |
| DBLP 对非 CS 领域覆盖弱 | 非 CS 退回 OpenAlex 主干；定位本就偏 CS |
| 跨源消歧错误（张冠李戴） | 姓名+机构+合作者重叠多信号；冲突标记而非武断合并 |
| 批量抓取触发限流 | 缓存 + 并发上限 + 退避重试 + 超时 |
| client 无 web search 时主页第 3 层失效 | 优雅降级：返回 search_query，标 unknown，不报错 |
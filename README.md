# Professor Fit MCP

帮 PhD 申请者匹配教授的 MCP server。输入研究兴趣关键词，输出带溯源与置信度的「教授匹配度」表格。

## 设计理念

**轻服务器（Thin Server）**：server 只做「LLM 做不到的事」——联网取数据、跨源整合、结构化输出；语义 fit 判断交给调用方的 client LLM（Claude / Cursor）。

- **OpenAlex 为主干**：免费、无需 API key、自带作者消歧与 h-index
- **多源交叉验证**：OpenAlex（指标/论文/concepts）+ DBLP（主页 URL / 首发年）+ 个人主页（职称/email/lab）
- **诚实数据**：每个关键字段带 `source` 与 `confidence`，拿不到就标 `unknown`，绝不编造
- **零 key 默认可用**：核心路径无需任何 API key

## 安装

推荐使用 [uv](https://github.com/astral-sh/uv)（需要 Python 3.10+）：

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
```

或使用 pip：

```bash
pip install -e .
```

## Cursor 配置

在 `~/.cursor/mcp.json` 中添加（Windows 路径示例）：

```json
{
  "mcpServers": {
    "professor-fit": {
      "command": "D:\\path\\to\\ProfessorFitMCP\\.venv\\Scripts\\professor-fit-mcp.exe",
      "env": {
        "OPENALEX_EMAIL": "your@email.com"
      }
    }
  }
}
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

> `OPENALEX_EMAIL` 可选——填写后 OpenAlex 进入「礼貌池」，速率更高。

## 使用

### 推荐：一键搜索（带 topic/domain 优先级）

直接用 `find_professors`，一次完成「意图分析 → 搜索 → 详情 → 排序 → 生成 Markdown 表格」：

```
帮我找 mev + defi 方向的美国 R1 院校教授
```

Cursor / Claude 会自动拆分 topic vs domain 并调用：

```python
find_professors(
    keywords=["MEV", "DeFi"],
    topic_keywords=["MEV", "maximal extractable value", "frontrunning"],
    domain_keywords=["DeFi", "decentralized finance", "blockchain"],
    topic_weight=3.0,    # topic 命中的论文得分 ×3
    domain_weight=1.0,   # domain 命中的论文得分 ×1
    regions=["US"],
    institution_tier=["R1"],
    limit=30,
    since_year=2018,
)
```

**关键词优先级**：`topic_keywords` 中的查询命中权重 ×3，确保做 MEV 的人排名远高于泛 DeFi/blockchain 研究者。Cursor 的 Claude 会从 tool docstring 中理解 topic/domain 语义，自动拆分——无需额外 LLM 成本。

返回 Markdown 表格并**自动保存**（路径在 `saved_to` 中）。

### 兼容模式

不提供 topic/domain 时仍可工作（向后兼容）：

```python
find_professors(
    keywords=["MEV", "DeFi"],
    regions=["US"],
    limit=10,
)
```

此时 server 自动分析意图：
1. 若配置了 `LLM_API_KEY` → 调用 LLM 分析 topic/domain
2. 否则 → 规则回退（多词短语=topic，单词=domain）

### 进阶：分步调用

需要精细控制时，可单独调用底层工具：

```python
1. search_professors(keywords=[...], topic_keywords=[...], domain_keywords=[...], regions=["US"])
2. get_professor_details(professor_id="A5023888391")
3. rank_fit(user_interests={"keywords": [...]}, professors=[...])
4. export_table(professors=[...], format="markdown", output_path="results.md")
```

## 工具

### 搜索与排序

| 工具 | 功能 |
|------|------|
| `find_professors` | **推荐入口**：一键完成 搜索→详情→排序→导出，结果自动沉淀到资料库 |
| `search_professors` | 按研究方向粗筛候选教授（OpenAlex works→authors） |
| `get_professor_details` | 多源详情聚合（OpenAlex + DBLP + 主页），自动写入资料库 |
| `rank_fit` | 短语匹配粗排 + 打包精排材料供 client LLM 判断 |
| `export_table` | 输出表格，默认 `markdown`，可选 `csv` / `json` |

### 资料库管理

| 工具 | 功能 |
|------|------|
| `update_professor_profile` | 手动更新教授档案字段（主页、职位、PI 状态、研究 tag、notes） |
| `add_web_search_evidence` | 写入 WebSearch 证据并触发多源交叉验证合并 |
| `profiles_inspect` | 查看资料库统计、按姓名/学校/tag/验证状态查询，或查看单个教授完整档案+证据 |
| `profiles_export` | 导出资料库为 `json` / `markdown` / `csv`，可选包含证据 |

### 筛选参数

- `regions`：`US`, `UK`/`GB`, `JP`, `KR`, `DE`, `CA`, `AU`, `SG`, `HK`, `ASIA`, `ALL`
- `institution_tier`：`R1`（美）, `HK5`（港五校）, `Russell`（英）, `Go8`（澳）, `U15`（加）, `TU9`（德）, `Imperial`（日）, `SKY`（韩）
- `topic_keywords`：核心研究课题（教授必须直接做这个方向）。高评分权重。
- `domain_keywords`：领域上下文（教授在这个大领域中工作）。低评分权重。
- `topic_weight` / `domain_weight`：topic/domain 查询的得分倍数（默认 3.0 / 1.0）
- `required_keywords`：领域锚点（命中任一即保留）。**不传时自动推断**；传 `[]` 关闭闸门
- `min_relevance`：最低相关分阈值（0.0–1.0）
- `since_year`：论文起始年份（默认 current_year - 7）

## 精度与召回

- **关键词优先级**：topic 查询命中的论文得分是 domain 的 3-4.5 倍，确保核心研究方向的人排名靠前，不被宽泛领域的高产作者冲淡。
- **召回**：搜索按「topic/domain 分组查询 + 领域同义词扩展（最多 8 条）+ 深翻页（5 页×100）+ 并发解析作者（上限 200 人）」展开候选池。
- **机构准确性（五级回退）**：
  1. OpenAlex `last_known_institutions`
  2. OpenAlex 历年 `affiliations`（5 年窗口）
  3. 论文级 authorship 中标注的机构（最及时）
  4. DBLP 策展 affiliation（人工维护，最准确）
  5. InstitutionClassifier 模糊匹配
- **精度闸门**：默认按领域核心词做 ANY-match 过滤，排除邻域误报。

## 主页发现策略

```
1. DBLP person record 的 <url> 标签       ← server，排除 scholar/orcid 等聚合站
2. OpenAlex 作者 homepage（若有）          ← server，免费
3. 仍无 → 返回 homepage_search_query +     ← 交 client（Cursor/Claude）的 web search
        homepage_resolution 指令              补全个人/院系主页（多数教授都有主页）
```

`find_professors` 的返回里含 `homepage_resolution.needed` 列表，client 应对其中每个 `search_query` 做 web 搜索补全主页（顺带可验证职称/当前任职）。

## 教授资料库

每次搜索/查详情会自动将教授档案写入本地 SQLite 数据库 `professor_profiles.db`（路径可通过 `PROFESSOR_PROFILES_DB_PATH` 环境变量配置）。

资料库存储：
- 身份：姓名、学校、国家、tier、职位、是否 PI
- 指标：h-index、citations、works_count、近 3 年论文
- 研究内容：OpenAlex concepts、研究方向 tags、最近论文（JSON）
- 主页：URL + 来源 + 验证时间
- 验证状态：`verified` / `needs_review` / `unverified`

### 多源交叉验证

WebSearch 证据通过 `add_web_search_evidence` 写入，自动与 OpenAlex/DBLP 数据合并。合并按来源优先级进行：

- 主页 URL：院系 faculty page > 个人主页 > DBLP > OpenAlex
- 职位/PI：faculty page > 个人主页 > 启发式推断
- 机构：faculty page > OpenAlex affiliations > DBLP

来源冲突时标记 `needs_review`，不静默覆盖。

### 查看资料库

```python
profiles_inspect()                                    # 统计概览
profiles_inspect(name="Ari Juels")                    # 按姓名搜索
profiles_inspect(openalex_id="A5023888391")           # 完整档案+证据
profiles_export(format="json", output_path="db.json") # 导出为文件
```

## 开发

```bash
# 运行测试
uv run pytest tests/ -v
```

## 环境变量

| 变量 | 必须 | 说明 |
|------|------|------|
| `OPENALEX_EMAIL` | 否 | 填写后进入 OpenAlex 礼貌池，速率更高 |
| `PROFESSOR_PROFILES_DB_PATH` | 否 | 资料库路径（默认 `professor_profiles.db`） |
| `PROFESSOR_FIT_OUTPUT_DIR` | 否 | Markdown 结果保存目录（默认项目根） |
| `LLM_API_KEY` | 否 | LLM 意图分析（仅 fallback 路径需要，Cursor 中不需要） |
| `LLM_BASE_URL` | 否 | LLM API 地址（默认 OpenAI，兼容 Deepseek 等） |
| `LLM_MODEL` | 否 | LLM 模型名（默认 `gpt-4o-mini`） |

## 数据源

| 数据源 | 角色 | API key |
|--------|------|---------|
| OpenAlex | 主干：指标/机构/concepts/论文/作者消歧 | 否 |
| DBLP | CS 发表记录、主页 URL、当前机构、首发年（全量并发查询） | 否 |
| 个人主页 | best-effort：职称/email/lab/招生信号 | 否 |
| 院校分级 | 内置 JSON（R1/HK5/Russell 等） | 否 |
| LLM（可选） | 查询意图分析：topic/domain 拆分 + 同义词扩展 + 拼写纠错 | 可选 |
| professor_profiles.db | 本地资料库：持久化档案 + WebSearch 证据 + 交叉验证 | 否 |

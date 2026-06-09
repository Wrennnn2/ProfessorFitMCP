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
2. get_professor_details(professor_id="A123...")
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

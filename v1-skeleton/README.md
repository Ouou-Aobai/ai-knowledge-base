# AI 知识库系统

自动化技术情报收集与分析系统，持续追踪 GitHub Trending、Hacker News 等来源，通过 Agent 协作流水线将分散的技术资讯转化为结构化、可检索的知识条目。

## 项目结构

```
v1-skeleton/
├── scripts/collector.py              # 数据采集脚本
├── requirements.txt                  # Python 依赖
├── .env.example                      # 环境变量模板
├── knowledge/                        # 数据存储目录
│   ├── raw/                          # 原始采集数据
│   └── articles/                     # 整理后的知识条目
├── specs/project-vision.md           # 项目愿景文档
└── AGENTS.md                         # Agent 协作规范
```

## 快速开始

### 1. 安装依赖

```bash
cd v1-skeleton
pip install -r requirements.txt
```

### 2. 配置环境变量

复制环境变量模板并填写你的 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
- `GITHUB_TOKEN`: GitHub Personal Access Token（可选，用于提高 API 限额）
- `DEEPSEEK_API_KEY`: DeepSeek API 密钥（用于后续分析）
- `DASHSCOPE_API_KEY`: DashScope API 密钥（备用）

### 3. 运行数据采集

```bash
python scripts/collector.py
```

数据将保存到 `knowledge/raw/` 目录：
- `github-trending-YYYY-MM-DD.json`
- `hackernews-top-YYYY-MM-DD.json`

## 数据采集策略

### GitHub Trending
- **来源**: GitHub Search API
- **过滤**: AI/LLM/Agent 相关关键词
- **数量**: 前 50 个相关仓库
- **频率**: 每日一次

### Hacker News
- **来源**: Hacker News Firebase API
- **过滤**: 标题或 URL 包含 AI 关键词
- **数量**: 前 30 个相关文章
- **频率**: 每日一次

### AI 关键词列表
包括: ai, ml, llm, gpt, chatgpt, claude, agent, rag, diffusion, transformer, neural network, deep learning 等

## 输出格式

### 原始数据文件示例
```json
{
  "source": "github",
  "collected_at": "2026-04-19T10:30:00Z",
  "count": 25,
  "items": [
    {
      "id": "openai/agents-sdk",
      "title": "agents-sdk",
      "description": "OpenAI Agents SDK for building agentic AI applications",
      "url": "https://github.com/openai/agents-sdk",
      "stars": 15200,
      "language": "Python",
      "topics": ["ai", "agents", "openai", "llm"],
      "created_at": "2026-03-10T08:00:00Z",
      "updated_at": "2026-03-17T06:30:00Z"
    }
  ]
}
```

## 自动化部署

### GitHub Actions 配置示例
创建 `.github/workflows/collect.yml`:

```yaml
name: Daily Data Collection
on:
  schedule:
    - cron: '0 0 * * *'  # 每天 UTC 00:00 运行
  workflow_dispatch:      # 支持手动触发

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: pip install -r requirements.txt
        
      - name: Run collector
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python scripts/collector.py
        
      - name: Commit and push changes
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add knowledge/raw/
          git commit -m "chore: update data for $(date +'%Y-%m-%d')" || echo "No changes to commit"
          git push
```

## 后续步骤

1. **配置 GitHub Actions**：实现每日自动采集
2. **集成 Tavily API**：分析内容相关性并生成摘要
3. **接入飞书多维表格**：可视化展示数据
4. **人工审核发布**：选择内容发布到小红书/公众号

## 注意事项

- GitHub API 有限额，建议使用 `GITHUB_TOKEN`
- Hacker News API 无需认证，但请控制请求频率
- 脚本具有幂等性，重复运行不会产生重复数据
- 所有时间戳使用 ISO 8601 格式
- 文本编码为 UTF-8，支持中文
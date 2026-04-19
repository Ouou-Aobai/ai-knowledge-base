# AI 知识库 · 项目愿景 v0.3

## 项目定位（核心变更）

> **这不是一个作业，是一个真实的每日情报流。**
> 目标：替代鳌拜每天早上的"AI Trending 汇报"，让我产出的不是一段聊天记录，而是一个经过分析、可直接用于内容决策的结构化知识库。

---

## 项目概述

**AI Knowledge Base（AI 知识库）** 是一个自动化技术情报收集与分析系统，持续追踪 GitHub Trending、Hacker News 等来源，通过 Agent 协作流水线将分散的技术资讯转化为结构化、可检索的知识条目，最终支持小红书和公众号的内容创作。

**核心价值**：让 AI 情报收集不再是黑箱，而是一个透明、可追溯、可编辑的知识库。

---

## 核心价值主张

1. **全自动化采集**：GitHub Actions 定时触发，无需人工值守
2. **结构化分析**：Tavily API 提供 relevance_score + 摘要，不是聊天记录
3. **透明可编辑**：JSON 存储 + 飞书多维表格呈现，任何条目都可以人工修改
4. **多平台发布支持**：小红书（手动）+ 公众号（手动），AI 负责采集分析，人负责最终决策

---

## Agent 协作架构

```
[Collector] ──采集原始数据──→ knowledge/raw/
                                    │
[Tavily API] ──分析+打分──→ knowledge/enriched/
                                    │
[Organizer] ──整理索引──→ knowledge/articles/
                                    │
                            ┌───────┴───────┐
                            ↓               ↓
                    飞书多维表格        JSON索引文件
                    （可视化查阅）     （机器可读）
                            ↓
                    人工审核 → 小红书发布 / 公众号发布
```

### Agent 职责

- **Collector**：从 GitHub Trending、Hacker News 抓取原始内容
- **Tavily Analyzer**：调用 Tavily Search API，获取 relevance_score + 技术摘要 + 相关标签
- **Organizer**：整理为标准化 JSON 条目，更新飞书多维表格

---

## 数据源（v0.3 精简版）

| 数据源 | 包含 | 理由 |
|--------|------|------|
| GitHub Trending | ✅ | 已有脚本可用，内容质量高，AI 相关性强 |
| Hacker News | ✅ | Firebase 公开 API，rate limit 够用，内容偏技术 |

**暂不包含**：
- arXiv：VPN 环境下访问不稳定；论文内容偏学术，与小红书受众距离远
- Twitter/X：API 访问受限，不稳定

**抓取频率**：每日一次（GitHub Actions UTC 00:00）

**抓取数量**：
- GitHub Trending：前 50 条，过滤 AI 相关关键词（ai/ml/llm/agent/gpt/diffusion）
- Hacker News：Top 30 条，过滤含 AI 相关词的条目

---

## 分析流程（v0.3 真实方案）

```
原始条目
    ↓
Tavily Search API（一次调用一个 URL）
    ↓ 返回 relevance_score（0-1）+ summary（英文）
    ↓
规则打标签（基于 title/URL 关键词）
    ↓
中文摘要生成（我来做，或者 GPT-4o）
    ↓
结构化 JSON 条目
    ↓
写入飞书多维表格（我直接用 Python API 写）
```

**relevance_score 阈值**：≥ 0.6 进入知识库

---

## 知识条目字段（精简到 8 个）

```json
{
  "id": "uuid",
  "title": "原始标题（英文）",
  "title_cn": "中文标题（人工或 GPT 翻译）",
  "source": "github / hackernews",
  "url": "原文链接",
  "collected_at": "ISO 8601 时间",
  "relevance_score": 0.0-1.0,
  "summary": "Tavily 返回的英文摘要",
  "summary_cn": "中文摘要（人工补充）",
  "tags": ["ai", "agent", "llm"],
  "published": false,
  "published_at": null,
  "platform": null
}
```

---

## 系统边界

### ✅ 包含

- 自动化采集（GitHub Actions）
- 结构化分析（Tavily API）
- 透明存储（JSON + 飞书多维表格）
- 人工审核 → 小红书 / 公众号发布

### ❌ 不包含

- 用户界面 / 认证系统
- 自动发布到小红书或公众号（人工操作）
- 实时推送
- 评论 / 社交功能

---

## 与现有流程的关系

**当前（鳌拜 Trending 汇报）**：
```
我每天早上搜索 → 给你一段聊天记录 → 你自己判断哪些有用
缺点：分散在聊天记录里，不可检索，不可复用
```

**目标（AI 知识库）**：
```
GitHub Actions 定时跑 → Tavily 分析 → 飞书多维表格 → 你每天早上打开表格看一眼 → 决定今天发什么
优点：透明、可检索、可编辑、可追溯
```

---

## 验收标准

### 功能验收

1. GitHub Actions 每日成功运行（成功率 ≥ 90%）
2. relevance_score ≥ 0.6 的条目 ≥ 10 条/天
3. 飞书多维表格实时更新，你每天早上能直接打开看

### 质量验收

1. 每天花 5 分钟抽检 3 条，确认摘要准确
2. tags 准确率 ≥ 70%（前期允许规则误差）
3. 数据完整率（必填字段）100%

---

## 扩展路线图

### Phase 1（现在 ~ 2 周）
- GitHub Trending + Hacker News 采集
- Tavily 分析 + relevance_score
- 飞书多维表格展示
- **你每天早上：打开表格 → 选 1-2 条 → 写小红书**

### Phase 2（1 个月后）
- 加入微信公众号文章采集（OpenCLI 已可用）
- 中文摘要生成（GPT-4o 或我来做）
- 公众号排版模板

### Phase 3（未来）
- Twitter/X 采集（视 API 稳定性）
- 自动生成小红书草稿（你在基础上改）

---

## 下一步

1. 本文档确认后 → Stage 3 Implement 写采集脚本
2. 脚本跑通 → 配置 GitHub Actions 定时任务
3. 定时跑通 → 接入飞书多维表格
4. 表格可用 → 你每天早上的情报消费习惯切过来

---

*v0.3 · 2026-04-19 · 定位从作业调整为真实产品*

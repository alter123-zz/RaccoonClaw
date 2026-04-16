---
name: arxiv-reader
description: "Fetches arXiv papers by ID or URL, summarizes abstracts and key findings, explains methodology, extracts citations, and compares multiple papers side by side. Use when the user shares an arXiv link, asks to read or summarize a research paper, or wants to compare academic literature. Keywords: 论文, arXiv, paper, preprint, research paper, summarize paper, arxiv.org."
---

# 论文阅读助手 — 对话式阅读arXiv论文，自动总结和对比分析

## 概述

对话式阅读arXiv论文，适用于科研人员和学生快速阅读论文、提取关键贡献、对比多篇论文方法差异、生成文献综述摘要等场景。

## 前置依赖

```bash
pip install arxiv requests beautifulsoup4
```

## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `search` | 按关键词或arXiv ID搜索论文，返回标题、摘要、作者、日期 | `python3 scripts/arxiv_reader_tool.py search <关键词或ID>` |
| `parse` | 下载论文PDF并提取全文内容、章节结构、公式、表格 | `python3 scripts/arxiv_reader_tool.py parse <arXiv ID>` |
| `compare` | 对比多篇论文的方法、数据集、结果差异 | `python3 scripts/arxiv_reader_tool.py compare <ID1> <ID2> [ID3...]` |

## 使用流程

### 步骤1：搜索或定位论文

```bash
# 按ID获取论文元数据
python3 scripts/arxiv_reader_tool.py search 2401.04088

# 按关键词搜索最近论文
python3 scripts/arxiv_reader_tool.py search 'LLM Agent' --days 7
```

**验证**: 确认返回的论文标题和摘要与预期匹配。如果ID无效，脚本会返回错误提示。

### 步骤2：解析论文全文

```bash
python3 scripts/arxiv_reader_tool.py parse 2401.04088
```

**验证**: 确认输出包含完整的章节结构（Introduction, Methods, Results等）。如果PDF下载失败，检查网络连接并重试。

### 步骤3：多篇论文对比（可选）

```bash
python3 scripts/arxiv_reader_tool.py compare 2401.04088 2312.12456 2310.09876
```

**验证**: 确认对比表包含每篇论文的方法、数据集和关键结果。

## 输出格式

```markdown
# 论文阅读报告

## 论文信息
| 字段 | 内容 |
|------|------|
| 标题 | [论文标题] |
| 作者 | [作者列表] |
| 发布日期 | [YYYY-MM-DD] |
| arXiv ID | [ID] |

## 摘要
[论文摘要原文或翻译]

## 关键贡献
1. [主要贡献1]
2. [主要贡献2]

## 方法论
[核心方法描述]

## 实验结果
| 指标 | 本文方法 | 基线方法 | 提升 |
|------|----------|----------|------|
| [指标名] | [数值] | [数值] | [差异] |

## 局限性与未来方向
[作者指出的局限性和后续研究方向]
```

## 参考资料

- [arXiv官方API文档](https://arxiv.org/help/api/user-manual)
- [arxiv.py — Python arXiv API封装库](https://github.com/lukasschwab/arxiv.py)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 首次使用请先安装Python依赖：`pip install arxiv requests beautifulsoup4`

---
name: arxiv-reader
description: "arXiv论文智能阅读助手。通过对话式交互阅读和分析学术论文。Keywords: 论文, arXiv, paper, academic research."
---

# 论文阅读助手 — 对话式阅读arXiv论文，自动总结和对比分析

## 概述

对话式阅读arXiv论文，自动总结和对比分析。适用于科研人员和学生快速阅读论文、提取关键贡献、对比多篇论文方法差异、生成文献综述摘要等场景。

**触发关键词**: 论文, arXiv, paper, academic research

## 前置依赖

```bash
pip install arxiv requests beautifulsoup4
```

## 核心能力

### 能力1：arXiv论文搜索和元数据获取（标题/摘要/作者/日期）
arXiv论文搜索和元数据获取（标题/摘要/作者/日期）

### 能力2：论文PDF下载和全文解析提取
论文PDF下载和全文解析提取

### 能力3：多篇论文对比分析和文献综述生成
多篇论文对比分析和文献综述生成


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `search` | 搜索arXiv论文 (关键词/ID) | `python3 scripts/arxiv_reader_tool.py search [参数]` |
| `parse` | 解析论文PDF提取关键内容 | `python3 scripts/arxiv_reader_tool.py parse [参数]` |
| `compare` | 多篇论文方法对比 | `python3 scripts/arxiv_reader_tool.py compare [参数]` |


## 使用流程

### 场景 1

```
帮我阅读 2401.04088 这篇论文，总结主要贡献和方法论
```

**执行：**
```bash
python3 scripts/arxiv_reader_tool.py search 2401.04088
```

### 场景 2

```
对比这3篇Transformer论文的方法差异
```

**执行：**
```bash
python3 scripts/arxiv_reader_tool.py compare 2401.04088 2312.12456 2310.09876
```

### 场景 3

```
搜索最近一周关于LLM Agent的论文
```

**执行：**
```bash
python3 scripts/arxiv_reader_tool.py search 'LLM Agent' --days 7
```


## 输出格式

```markdown
# 📊 论文阅读助手报告

**生成时间**: YYYY-MM-DD HH:MM

## 核心发现
1. [关键发现1]
2. [关键发现2]
3. [关键发现3]

## 数据概览
| 指标 | 数值 | 趋势 | 评级 |
|------|------|------|------|
| 指标A | XXX | ↑ | ⭐⭐⭐⭐ |
| 指标B | YYY | → | ⭐⭐⭐ |

## 详细分析
[基于实际数据的多维度分析内容]

## 行动建议
| 优先级 | 建议 | 预期效果 |
|--------|------|----------|
| 🔴 高 | [具体建议] | [量化预期] |
| 🟡 中 | [具体建议] | [量化预期] |
| 🟢 低 | [具体建议] | [量化预期] |
```

## 参考资料

### API文档
- [arXiv官方API文档，论文检索和元数据获取接口](https://arxiv.org/help/api/user-manual)
### GitHub
- [GitHub: arxiv.py — Python arXiv API封装库，支持搜索下载和解析论文](https://github.com/lukasschwab/arxiv.py)
- [GitHub: arXiv论文阅读器Agent用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/arxiv-paper-reader.md)
### HackerNews
- [HackerNews: 用LLM自动阅读和总结arXiv论文的讨论](https://news.ycombinator.com/item?id=38856140)
### Reddit
- [Reddit r/MachineLearning: 最佳arXiv论文阅读工具讨论](https://www.reddit.com/r/MachineLearning/comments/18xqn7a/d_best_tools_for_reading_arxiv_papers/)
### 微信公众号
- [微信公众号「AI科技评论」: 如何高效阅读arXiv论文的AI工具推荐](https://mp.weixin.qq.com/s/HdGYrXGzijKqDjPJ2GCKWQ)
### 小红书
- [小红书: 用AI工具批量阅读论文的方法分享](https://www.xiaohongshu.com/explore/65a1d2e3000000001e03456a)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install arxiv requests beautifulsoup4`

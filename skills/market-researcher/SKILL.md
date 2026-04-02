---
name: market-researcher
description: "市场调研自动化工具。从社交媒体挖掘用户痛点，分析竞品。Keywords: 市场调研, 竞品分析, market research."
---

# 市场调研自动化 — 从社交媒体挖掘用户痛点分析竞品

## 概述

从社交媒体挖掘用户痛点分析竞品。适用于产品立项前市场验证、用户需求分析、竞品功能对比等场景。

**触发关键词**: 市场调研, 竞品分析, market research

## 前置依赖

```bash
pip install requests beautifulsoup4 pandas
```

## 核心能力

### 能力1：市场规模估算——TAM/SAM/SOM三层模型
市场规模估算——TAM/SAM/SOM三层模型

### 能力2：竞品深度分析——功能/定价/用户评价对比矩阵
竞品深度分析——功能/定价/用户评价对比矩阵

### 能力3：用户访谈框架和调研问卷自动生成
用户访谈框架和调研问卷自动生成


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `research` | 市场调研 | `python3 scripts/market_researcher_tool.py research [参数]` |
| `compete` | 竞品分析 | `python3 scripts/market_researcher_tool.py compete [参数]` |
| `survey` | 生成调研问卷 | `python3 scripts/market_researcher_tool.py survey [参数]` |


## 使用流程

### 场景 1

```
调研AI写作工具市场竞品
```

**执行：**
```bash
python3 scripts/market_researcher_tool.py research --market 'AI写作工具'
```

### 场景 2

```
对比5个竞品的功能和定价
```

**执行：**
```bash
python3 scripts/market_researcher_tool.py compete --products 'Jasper,Copy.ai,Notion AI'
```

### 场景 3

```
生成用户调研问卷
```

**执行：**
```bash
python3 scripts/market_researcher_tool.py survey --topic 'AI写作工具'
```


## 输出格式

```markdown
# 📊 市场调研自动化报告

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

### 原有链接
- [X/Twitter API，用户讨论数据](https://developer.x.com/en/docs/x-api)
- [市场研究Agent完整用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/market-research-product-factory.md)
- [Google Trends，搜索趋势分析](https://www.google.com/trends/)
### HackerNews
- [HackerNews: AI市场调研工具和方法](https://news.ycombinator.com/item?id=46519758)
### Reddit
- [Reddit r/Entrepreneur: Entrepreneur社区AI相关讨论](https://www.reddit.com/r/Entrepreneur/comments/10a26d9yyz/market_researcher_ai/)
### 微信公众号
- [微信公众号: AI市场调研——社交媒体需求挖掘](https://mp.weixin.qq.com/s/ZNVSWHXFEFAPBCDWBRSLDM)
### 小红书
- [小红书: AI市场调研——从社交媒体挖掘用户痛点](https://www.xiaohongshu.com/explore/495513637729942002335075)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests beautifulsoup4 pandas`

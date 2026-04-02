---
name: earnings-tracker
description: "公司财报追踪器。自动追踪科技公司财报发布日期并生成摘要。Keywords: 财报, earnings, financial report."
---

# 财报追踪器 — 自动追踪科技公司财报并生成投资摘要

## 概述

自动追踪科技公司财报并生成投资摘要。适用于投资者追踪重仓公司财报日历、自动汇总财报亮点和风险等场景。

**触发关键词**: 财报, earnings, financial report

## 前置依赖

```bash
pip install yfinance requests pandas
```

## 核心能力

### 能力1：财报日历追踪——自动获取目标公司财报发布日期
财报日历追踪——自动获取目标公司财报发布日期

### 能力2：市场预期对比——EPS/营收预期vs实际
市场预期对比——EPS/营收预期vs实际

### 能力3：财报解读——关键指标变化和管理层指引摘要
财报解读——关键指标变化和管理层指引摘要


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `track` | 追踪财报日期 | `python3 scripts/earnings_tracker_tool.py track [参数]` |
| `preview` | 财报预览分析 | `python3 scripts/earnings_tracker_tool.py preview [参数]` |
| `review` | 财报解读 | `python3 scripts/earnings_tracker_tool.py review [参数]` |


## 使用流程

### 场景 1

```
追踪苹果下次财报日期和市场预期
```

**执行：**
```bash
python3 scripts/earnings_tracker_tool.py track AAPL
```

### 场景 2

```
财报发布前的预期分析
```

**执行：**
```bash
python3 scripts/earnings_tracker_tool.py preview AAPL
```

### 场景 3

```
解读最新财报关键数据
```

**执行：**
```bash
python3 scripts/earnings_tracker_tool.py review AAPL --quarter Q1
```


## 输出格式

```markdown
# 📊 财报追踪器报告

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
- [Financial Modeling Prep API，财报数据](https://site.financialmodelingprep.com/developer/docs)
- [腾讯云量化投资技术参考](https://www.tencentcloud.com/techpedia/140877)
- [yfinance库，财报日历和收益数据](https://pypi.org/project/yfinance/)
### GitHub
- [GitHub: yfinance——财报日历和收益数据](https://github.com/ranaroussi/yfinance)
### HackerNews
- [HackerNews: 自动追踪和分析财报的AI工具](https://news.ycombinator.com/item?id=41536932)
### Reddit
- [Reddit r/investing: investing社区AI相关讨论](https://www.reddit.com/r/investing/comments/1012d42yyz/earnings_tracker_ai/)
### 微信公众号
- [微信公众号: AI财报分析——追踪重仓公司业绩](https://mp.weixin.qq.com/s/UHESQGOCGJHBEYVTVHWRJV)
### 小红书
- [小红书: AI追踪重仓公司财报日历](https://www.xiaohongshu.com/explore/658200002929366595881683)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install yfinance requests pandas`

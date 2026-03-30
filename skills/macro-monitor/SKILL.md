---
name: macro-monitor
description: "宏观经济指标监控器。追踪GDP、利率、CPI等关键宏观经济数据和央行政策。Keywords: 宏观经济, GDP, 利率, CPI, macro, interest rate."
---

# 宏观经济监控 — 追踪GDP利率CPI等宏观经济指标

## 概述

追踪GDP利率CPI等宏观经济指标。适用于投资者判断宏观经济周期、评估利率变动影响、资产配置大方向调整等场景。

**触发关键词**: 宏观经济, GDP, 利率, CPI, macro, interest rate

## 前置依赖

```bash
pip install requests pandas matplotlib
```

## 核心能力

### 能力1：宏观经济指标监控——GDP/CPI/PMI/社融等
宏观经济指标监控——GDP/CPI/PMI/社融等

### 能力2：央行政策解读——利率/准备金率变化影响分析
央行政策解读——利率/准备金率变化影响分析

### 能力3：全球经济联动——美联储/ECB政策对A股影响
全球经济联动——美联储/ECB政策对A股影响


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `monitor` | 查看宏观指标 | `python3 scripts/macro_monitor_tool.py monitor [参数]` |
| `policy` | 政策解读 | `python3 scripts/macro_monitor_tool.py policy [参数]` |
| `impact` | 影响分析 | `python3 scripts/macro_monitor_tool.py impact [参数]` |


## 使用流程

### 场景 1

```
查看最新CPI和PMI数据
```

**执行：**
```bash
python3 scripts/macro_monitor_tool.py monitor --indicators CPI,PMI
```

### 场景 2

```
分析当前利率环境对A股影响
```

**执行：**
```bash
python3 scripts/macro_monitor_tool.py impact --topic interest_rate
```

### 场景 3

```
分析最新宏观经济形势
```

**执行：**
```bash
python3 scripts/macro_monitor_tool.py policy --latest
```


## 输出格式

```markdown
# 📊 宏观经济监控报告

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
- [FRED API，美联储GDP/CPI/利率数据](https://fred.stlouisfed.org/docs/api/fred/)
- [腾讯云宏观经济分析参考](https://www.tencentcloud.com/techpedia/140877)
- [世界银行全球宏观经济数据](https://data.worldbank.org/)
### GitHub
- [GitHub: Python FRED经济数据API客户端](https://github.com/mortada/fredapi)
### HackerNews
- [HackerNews: 宏观经济指标追踪和AI预测](https://news.ycombinator.com/item?id=43336298)
### Reddit
- [Reddit r/economics: economics社区AI相关讨论](https://www.reddit.com/r/economics/comments/10a05d0yyz/macro_monitor_ai/)
### 微信公众号
- [微信公众号: AI宏观经济分析——趋势解读](https://mp.weixin.qq.com/s/BZKSYWZMQWTETVVUBRNZPT)
### 小红书
- [小红书: AI宏观经济分析——GDP CPI利率解读](https://www.xiaohongshu.com/explore/394664067082645199431226)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests pandas matplotlib`

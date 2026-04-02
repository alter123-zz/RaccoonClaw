---
name: analytics-dashboard
description: "数据看板。业务数据看板生成器。自动搭建KPI监控看板、实时指标追踪、定期自动报告推送 Keywords: 数据看板, dashboard, KPI监控, 业务分析."
---

## 概述

业务数据看板生成器。自动搭建KPI监控看板、实时指标追踪、定期自动报告推送 适用于搭建业务数据看板等场景。

## 适用范围

**适用场景**：
- 搭建业务数据看板
- 设置KPI监控告警
- 自动生成周报月报

**不适用场景**：
- 需要实时硬件控制或低延迟响应的场景
- 涉及敏感个人隐私数据的未授权处理

**触发关键词**: 数据看板, dashboard, KPI监控, 业务分析

## 前置条件

```bash
pip install plotly dash pandas
```

> ⚠️ 首次使用前请确认依赖已安装，否则脚本将无法运行。

## 核心能力

### 能力1：看板搭建——拖拽式KPI卡片/图表/表格
看板搭建——拖拽式KPI卡片/图表/表格

### 能力2：实时监控——指标阈值告警与趋势预测
实时监控——指标阈值告警与趋势预测

### 能力3：自动报告——日报/周报/月报自动生成推送
自动报告——日报/周报/月报自动生成推送


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `create` | 创建看板 | `python3 scripts/analytics_dashboard_tool.py create [参数]` |
| `monitor` | 指标监控 | `python3 scripts/analytics_dashboard_tool.py monitor [参数]` |
| `report` | 自动报告 | `python3 scripts/analytics_dashboard_tool.py report [参数]` |


## 处理步骤

### Step 1：创建看板

**目标**：创建销售看板

**为什么这一步重要**：这是整个工作流的数据采集/初始化阶段，确保后续步骤基于准确的输入。

**执行**：
```bash
python3 scripts/analytics_dashboard_tool.py create --data sales.csv --kpis 'revenue,orders,aov'
```

**检查点**：确认输出包含预期数据，无报错信息。

### Step 2：指标监控

**目标**：设置指标告警

**为什么这一步重要**：核心处理阶段，将原始数据转化为有价值的输出。

**执行**：
```bash
python3 scripts/analytics_dashboard_tool.py monitor --kpi revenue --threshold-min 10000 --notify email
```

**检查点**：确认生成结果格式正确，内容完整。

### Step 3：自动报告

**目标**：生成周报

**为什么这一步重要**：最终输出阶段，将处理结果以可用的形式呈现。

**执行**：
```bash
python3 scripts/analytics_dashboard_tool.py report --period week --compare-prev --format html
```

**检查点**：确认最终输出符合预期格式和质量标准。

## 验证清单

- [ ] 依赖已安装：`pip install plotly dash pandas`
- [ ] Step 1 执行无报错，输出数据完整
- [ ] Step 2 处理结果符合预期格式
- [ ] Step 3 最终输出质量达标
- [ ] 无敏感信息泄露（API Key、密码等）

## 输出格式

```markdown
# 📊 数据看板报告

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
```

## 参考资料

### 原有链接
- [Plotly Dash框架](https://dash.plotly.com/)

### GitHub
- [dashboard-tools](https://github.com/topics/dashboard)

### 小红书
- [数据看板设计](https://www.xiaohongshu.com/explore/dashboard)

## 注意事项

- 所有分析基于脚本获取的实际数据，**不编造数据**
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装依赖：`pip install plotly dash pandas`
- 如遇到API限流，请适当增加请求间隔

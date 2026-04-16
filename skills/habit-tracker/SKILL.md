---
name: habit-tracker
description: "Tracks daily habits with check-ins, calculates streaks and completion rates, and generates progress summaries with adaptive motivational coaching. Use when the user wants to track daily habits, maintain streaks, set up accountability check-ins, or needs motivational support for building routines. Keywords: 习惯, 打卡, 自律, habit tracker, accountability, streak, daily routine."
---

# 习惯打卡教练 — 每日签到追踪习惯连续天数

## 概述

每日签到追踪习惯连续天数，适用于早起打卡、读书打卡、运动打卡等习惯养成场景。支持每日/每周/自定义频率，自动计算连续天数和完成率，根据坚持情况调整激励策略。

## 前置依赖

```bash
pip install pandas requests
```

## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `create` | 创建新习惯，指定名称和打卡频率 | `python3 scripts/habit_tracker_tool.py create '早起6点' '阅读30分' '运动1小时'` |
| `check` | 记录今日打卡，更新连续天数 | `python3 scripts/habit_tracker_tool.py check --habit 阅读` |
| `stats` | 查看指定周期的完成统计和趋势 | `python3 scripts/habit_tracker_tool.py stats --period month` |

## 使用流程

### 步骤1：创建习惯

```bash
python3 scripts/habit_tracker_tool.py create '早起6点' '阅读30分' '运动1小时'
```

**验证**: 确认返回的习惯列表包含所有已创建项。如果习惯名称重复，脚本会提示冲突。

### 步骤2：每日打卡

```bash
python3 scripts/habit_tracker_tool.py check --habit 阅读
```

**验证**: 确认返回当前连续天数和今日打卡状态。同一天重复打卡会被忽略。

### 步骤3：查看统计

```bash
python3 scripts/habit_tracker_tool.py stats --period month
```

**验证**: 确认统计数据包含每个习惯的完成率和连续天数。

## 输出格式

```markdown
# 习惯打卡报告

**统计周期**: YYYY-MM-DD ~ YYYY-MM-DD

## 习惯概览
| 习惯 | 连续天数 | 本月完成率 | 状态 |
|------|----------|-----------|------|
| 早起6点 | 12天 | 85% | 🔥 连续中 |
| 阅读30分 | 3天 | 60% | ⚠️ 需加油 |
| 运动1小时 | 0天 | 30% | ❌ 已中断 |

## 本周打卡记录
| 日期 | 早起 | 阅读 | 运动 |
|------|------|------|------|
| 周一 | ✅ | ✅ | ❌ |
| 周二 | ✅ | ❌ | ✅ |

## 激励建议
- [基于当前数据的个性化建议]
```

## 参考资料

- [James Clear习惯追踪法](https://jamesclear.com/habit-tracker)
- [Habitica API — 游戏化习惯养成](https://habitica.com/apidoc/)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 首次使用请先安装Python依赖：`pip install pandas requests`

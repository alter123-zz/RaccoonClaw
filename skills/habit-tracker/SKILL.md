---
name: habit-tracker
description: "习惯追踪和问责教练。每日主动签到，追踪习惯连续天数，自适应激励。Keywords: 习惯, 打卡, 自律, habit tracker, accountability."
---

# 习惯打卡教练 — 每日主动签到追踪习惯连续天数

## 概述

每日主动签到追踪习惯连续天数。适用于早起打卡、读书打卡、运动打卡等习惯养成场景。

**触发关键词**: 习惯, 打卡, 自律, habit tracker, accountability

## 前置依赖

```bash
pip install pandas requests
```

## 核心能力

### 能力1：习惯打卡系统——支持每日/每周/自定义频率
习惯打卡系统——支持每日/每周/自定义频率

### 能力2：连续天数统计和习惯养成曲线
连续天数统计和习惯养成曲线

### 能力3：习惯关联分析——发现哪些习惯互相影响
习惯关联分析——发现哪些习惯互相影响


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `create` | 创建习惯 | `python3 scripts/habit_tracker_tool.py create [参数]` |
| `check` | 打卡 | `python3 scripts/habit_tracker_tool.py check [参数]` |
| `stats` | 查看统计 | `python3 scripts/habit_tracker_tool.py stats [参数]` |


## 使用流程

### 场景 1

```
创建习惯：早起6点/阅读30分/运动1小时
```

**执行：**
```bash
python3 scripts/habit_tracker_tool.py create '早起6点' '阅读30分' '运动1小时'
```

### 场景 2

```
打卡：今天完成了阅读
```

**执行：**
```bash
python3 scripts/habit_tracker_tool.py check --habit 阅读
```

### 场景 3

```
查看习惯完成统计
```

**执行：**
```bash
python3 scripts/habit_tracker_tool.py stats --period month
```


## 输出格式

```markdown
# 📊 习惯打卡教练报告

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
- [James Clear习惯追踪法，原子习惯策略](https://jamesclear.com/habit-tracker)
- [习惯追踪教练Agent完整用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/habit-tracker-accountability-coach.md)
- [Habitica API，游戏化习惯养成](https://habitica.com/apidoc/)
### HackerNews
- [HackerNews: AI习惯追踪工具和打卡机制](https://news.ycombinator.com/item?id=40612953)
### Reddit
- [Reddit r/theXeffect: theXeffect社区AI相关讨论](https://www.reddit.com/r/theXeffect/comments/1037775yyz/habit_tracker_ai/)
### 微信公众号
- [微信公众号: AI习惯教练——从打卡到养成好习惯](https://mp.weixin.qq.com/s/ZQYOBEDCMWNRXSZWGKPGRE)
### 小红书
- [小红书: 打卡100天——AI习惯教练帮我坚持](https://www.xiaohongshu.com/explore/475381930848192366370392)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install pandas requests`

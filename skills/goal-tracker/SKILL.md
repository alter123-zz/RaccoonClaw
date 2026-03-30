---
name: goal-tracker
description: "年度目标追踪管理器。设定目标、拆解为可执行计划、追踪进度。Keywords: 目标, 计划, 进度, goal, OKR, milestone."
---

# 年度目标追踪 — 设定目标拆解计划追踪里程碑进度

## 概述

设定目标拆解计划追踪里程碑进度。适用于年度OKR管理、个人成长目标追踪、项目里程碑监控等场景。

**触发关键词**: 目标, 计划, 进度, goal, OKR, milestone

## 前置依赖

```bash
pip install requests pandas
```

## 核心能力

### 能力1：OKR/SMART目标框架——自动拆解大目标为可执行子任务
OKR/SMART目标框架——自动拆解大目标为可执行子任务

### 能力2：进度可视化——完成率/里程碑/时间线追踪
进度可视化——完成率/里程碑/时间线追踪

### 能力3：定期回顾提醒——周回顾/月复盘自动生成
定期回顾提醒——周回顾/月复盘自动生成


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `set` | 设定目标 | `python3 scripts/goal_tracker_tool.py set [参数]` |
| `progress` | 查看进度 | `python3 scripts/goal_tracker_tool.py progress [参数]` |
| `review` | 生成回顾 | `python3 scripts/goal_tracker_tool.py review [参数]` |


## 使用流程

### 场景 1

```
设定年度目标：学Python，拆解月度计划
```

**执行：**
```bash
python3 scripts/goal_tracker_tool.py set '学Python' --deadline 2026-12-31 --method smart
```

### 场景 2

```
查看当前目标完成进度
```

**执行：**
```bash
python3 scripts/goal_tracker_tool.py progress --all
```

### 场景 3

```
生成本月目标回顾
```

**执行：**
```bash
python3 scripts/goal_tracker_tool.py review --period month
```


## 输出格式

```markdown
# 📊 年度目标追踪报告

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
- [Todoist API，目标拆解和任务管理](https://developer.todoist.com/rest/v2/)
- [任务管理器Agent用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/todoist-task-manager.md)
- [OKR方法论详解](https://www.whatmatters.com/faqs/okr-meaning-definition-example)
### HackerNews
- [HackerNews: AI目标追踪工具讨论](https://news.ycombinator.com/item?id=39723316)
### Reddit
- [Reddit r/selfimprovement: selfimprovement社区AI相关讨论](https://www.reddit.com/r/selfimprovement/comments/1092dbcyyz/goal_tracker_ai/)
### 微信公众号
- [微信公众号: AI目标管理——从设定到复盘全流程](https://mp.weixin.qq.com/s/JPBPRWAZDTCUVDFAJCKBVO)
### 小红书
- [小红书: 2026年度目标管理——AI拆解追踪OKR](https://www.xiaohongshu.com/explore/290858426654115013629307)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests pandas`

---
name: travel-planner
description: "AI旅行规划助手。自动生成个性化旅行计划，包含路线、住宿和预算。Keywords: 旅行, 攻略, travel plan, itinerary."
---

# AI旅行规划 — 自动生成个性化旅行计划含路线预算

## 概述

自动生成个性化旅行计划含路线预算。适用于制定旅行计划、景点路线规划、住宿比价、旅行预算控制等场景。

**触发关键词**: 旅行, 攻略, travel plan, itinerary

## 前置依赖

```bash
pip install requests geopy
```

## 核心能力

### 能力1：智能行程规划——根据天数/预算/偏好自动安排
智能行程规划——根据天数/预算/偏好自动安排

### 能力2：实时信息整合——天气/汇率/签证/交通
实时信息整合——天气/汇率/签证/交通

### 能力3：住宿和餐厅推荐——评分/价格/位置多维筛选
住宿和餐厅推荐——评分/价格/位置多维筛选


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `plan` | 生成旅行计划 | `python3 scripts/travel_planner_tool.py plan [参数]` |
| `budget` | 预算估算 | `python3 scripts/travel_planner_tool.py budget [参数]` |
| `checklist` | 出行清单 | `python3 scripts/travel_planner_tool.py checklist [参数]` |


## 使用流程

### 场景 1

```
规划5天日本东京自由行
```

**执行：**
```bash
python3 scripts/travel_planner_tool.py plan --dest Tokyo --days 5 --budget medium
```

### 场景 2

```
估算这趟旅行的费用
```

**执行：**
```bash
python3 scripts/travel_planner_tool.py budget --dest Tokyo --days 5 --from Shanghai
```

### 场景 3

```
生成出发前的准备清单
```

**执行：**
```bash
python3 scripts/travel_planner_tool.py checklist --dest Tokyo --season spring
```


## 输出格式

```markdown
# 📊 AI旅行规划报告

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
- [Google Places API，景点搜索和详情](https://developers.google.com/maps/documentation/places/web-service)
- [多渠道助手用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/multi-channel-assistant.md)
- [OpenWeatherMap API，天气预报](https://openweathermap.org/api)
### GitHub
- [GitHub: 交通旅游类免费API合集](https://github.com/public-apis/public-apis)
### HackerNews
- [HackerNews: AI旅行规划工具效果对比](https://news.ycombinator.com/item?id=46014902)
### Reddit
- [Reddit r/travel: travel社区AI相关讨论](https://www.reddit.com/r/travel/comments/102f1dfyyz/travel_planner_ai/)
### 微信公众号
- [微信公众号: AI旅行助手——自动生成个性化计划](https://mp.weixin.qq.com/s/JRPUTIOZUNREOQEYGJCAHZ)
### 小红书
- [小红书: 用AI规划7天日本自由行——行程+预算全攻略](https://www.xiaohongshu.com/explore/209538161365729613306448)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests geopy`

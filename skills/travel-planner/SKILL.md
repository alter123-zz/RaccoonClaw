---
name: travel-planner
description: "Generates day-by-day travel itineraries with transportation, hotel and restaurant recommendations, and daily budget estimates. Use when the user asks for trip planning, vacation itineraries, travel budget estimation, or destination recommendations. Keywords: 旅行, 攻略, travel plan, itinerary, 路线, 住宿, 预算, vacation, trip."
---

# AI旅行规划 — 自动生成个性化旅行计划含路线预算

## 概述

自动生成个性化旅行计划，适用于制定旅行计划、景点路线规划、住宿比价、旅行预算控制等场景。根据天数、预算和偏好自动安排行程，整合天气、交通等实时信息。

## 前置依赖

```bash
pip install requests geopy
```

## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `plan` | 根据目的地、天数和预算生成逐日行程 | `python3 scripts/travel_planner_tool.py plan --dest Tokyo --days 5 --budget medium` |
| `budget` | 估算整趟旅行的交通、住宿、餐饮费用 | `python3 scripts/travel_planner_tool.py budget --dest Tokyo --days 5 --from Shanghai` |
| `checklist` | 根据目的地和季节生成出发准备清单 | `python3 scripts/travel_planner_tool.py checklist --dest Tokyo --season spring` |

## 使用流程

### 步骤1：生成行程计划

```bash
python3 scripts/travel_planner_tool.py plan --dest Tokyo --days 5 --budget medium
```

**验证**: 确认输出包含逐日行程安排和景点列表。如果目的地无法识别，脚本会提示可用的目的地格式。

### 步骤2：估算预算

```bash
python3 scripts/travel_planner_tool.py budget --dest Tokyo --days 5 --from Shanghai
```

**验证**: 确认输出包含交通、住宿、餐饮各项费用明细。

### 步骤3：生成准备清单

```bash
python3 scripts/travel_planner_tool.py checklist --dest Tokyo --season spring
```

**验证**: 确认清单包含签证、货币、衣物、必备物品等分类。

## 输出格式

```markdown
# 旅行计划: [目的地] [天数]天

**出发地**: [城市]
**预算级别**: [经济/中等/高端]

## 逐日行程
### Day 1: [日期] — [主题]
| 时间 | 活动 | 地点 | 预估费用 |
|------|------|------|----------|
| 上午 | [活动] | [地点] | ¥XX |
| 下午 | [活动] | [地点] | ¥XX |
| 晚上 | [活动] | [地点] | ¥XX |

**住宿推荐**: [酒店名] — ¥XX/晚

## 预算总览
| 类别 | 预估费用 |
|------|----------|
| 交通（往返） | ¥XX |
| 住宿（X晚） | ¥XX |
| 餐饮 | ¥XX |
| 门票/活动 | ¥XX |
| **合计** | **¥XX** |

## 出行清单
- [ ] 签证/护照
- [ ] 货币兑换
- [ ] [季节相关衣物]
- [ ] 常用药品
```

## 参考资料

- [Google Places API](https://developers.google.com/maps/documentation/places/web-service)
- [OpenWeatherMap API](https://openweathermap.org/api)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 首次使用请先安装Python依赖：`pip install requests geopy`

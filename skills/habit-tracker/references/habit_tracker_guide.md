# 习惯打卡教练 — 分析框架与参考指南

## 工具概述

**名称**: 习惯打卡教练
**命令**: `create` (创建习惯), `check` (打卡), `stats` (查看统计)
**依赖**: `pip install pandas requests`

## 核心分析维度

- 习惯打卡系统——支持每日/每周/自定义频率
- 连续天数统计和习惯养成曲线
- 习惯关联分析——发现哪些习惯互相影响

## 分析框架

### 维度一：数据采集与整理
- 确定数据来源和采集范围
- 清洗和标准化原始数据
- 建立基准对比指标

### 维度二：深度洞察与模式识别
- 多维度交叉分析
- 历史趋势识别和未来预测
- 异常值检测和根因分析

### 维度三：行动建议与决策支持
- 基于数据的具体可执行建议
- 优先级排序（高/中/低）
- 风险评估和应对预案

## 评分标准

| 评分 | 等级 | 描述 | 行动建议 |
|------|------|------|----------|
| 5分 | ⭐⭐⭐⭐⭐ 优秀 | 远超预期 | 立即采纳 |
| 4分 | ⭐⭐⭐⭐ 良好 | 超出预期 | 优先执行 |
| 3分 | ⭐⭐⭐ 一般 | 符合预期 | 可选执行 |
| 2分 | ⭐⭐ 偏弱 | 低于预期 | 需要改进 |
| 1分 | ⭐ 不足 | 明显不足 | 建议规避 |

## 输出模板

```markdown
# 习惯打卡教练分析报告
## 核心发现
1. [发现1]
2. [发现2]

## 数据支撑
| 指标 | 数值 | 趋势 | 评级 |
|------|------|------|------|
| ... | ... | ... | ... |

## 行动建议
| 优先级 | 建议 | 依据 | 预期效果 |
|--------|------|------|----------|
| 🔴 高 | ... | ... | ... |
```

## 参考链接

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

## 使用提示

1. 本框架为习惯打卡教练专用分析模板，可根据具体场景调整
2. 评分标准可按实际需求微调权重
3. 建议结合定量数据和定性判断综合分析
4. 社交平台链接提供了该领域在小红书/Reddit/GitHub/HackerNews/X/微信公众号上的实际讨论和最佳实践，可作为分析参考

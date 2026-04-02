# 年度目标追踪 — 分析框架与参考指南

## 工具概述

**名称**: 年度目标追踪
**命令**: `set` (设定目标), `progress` (查看进度), `review` (生成回顾)
**依赖**: `pip install requests pandas`

## 核心分析维度

- OKR/SMART目标框架——自动拆解大目标为可执行子任务
- 进度可视化——完成率/里程碑/时间线追踪
- 定期回顾提醒——周回顾/月复盘自动生成

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
# 年度目标追踪分析报告
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

## 使用提示

1. 本框架为年度目标追踪专用分析模板，可根据具体场景调整
2. 评分标准可按实际需求微调权重
3. 建议结合定量数据和定性判断综合分析
4. 社交平台链接提供了该领域在小红书/Reddit/GitHub/HackerNews/X/微信公众号上的实际讨论和最佳实践，可作为分析参考

# 财报追踪器 — 分析框架与参考指南

## 工具概述

**名称**: 财报追踪器
**命令**: `track` (追踪财报日期), `preview` (财报预览分析), `review` (财报解读)
**依赖**: `pip install yfinance requests pandas`

## 核心分析维度

- 财报日历追踪——自动获取目标公司财报发布日期
- 市场预期对比——EPS/营收预期vs实际
- 财报解读——关键指标变化和管理层指引摘要

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
# 财报追踪器分析报告
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

## 使用提示

1. 本框架为财报追踪器专用分析模板，可根据具体场景调整
2. 评分标准可按实际需求微调权重
3. 建议结合定量数据和定性判断综合分析
4. 社交平台链接提供了该领域在小红书/Reddit/GitHub/HackerNews/X/微信公众号上的实际讨论和最佳实践，可作为分析参考

# 宏观经济监控 — 分析框架与参考指南

## 工具概述

**名称**: 宏观经济监控
**命令**: `monitor` (查看宏观指标), `policy` (政策解读), `impact` (影响分析)
**依赖**: `pip install requests pandas matplotlib`

## 核心分析维度

- 宏观经济指标监控——GDP/CPI/PMI/社融等
- 央行政策解读——利率/准备金率变化影响分析
- 全球经济联动——美联储/ECB政策对A股影响

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
# 宏观经济监控分析报告
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

## 使用提示

1. 本框架为宏观经济监控专用分析模板，可根据具体场景调整
2. 评分标准可按实际需求微调权重
3. 建议结合定量数据和定性判断综合分析
4. 社交平台链接提供了该领域在小红书/Reddit/GitHub/HackerNews/X/微信公众号上的实际讨论和最佳实践，可作为分析参考

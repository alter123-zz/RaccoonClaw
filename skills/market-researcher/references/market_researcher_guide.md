# 市场调研自动化 — 分析框架与参考指南

## 工具概述

**名称**: 市场调研自动化
**命令**: `research` (市场调研), `compete` (竞品分析), `survey` (生成调研问卷)
**依赖**: `pip install requests beautifulsoup4 pandas`

## 核心分析维度

- 市场规模估算——TAM/SAM/SOM三层模型
- 竞品深度分析——功能/定价/用户评价对比矩阵
- 用户访谈框架和调研问卷自动生成

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
# 市场调研自动化分析报告
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
- [X/Twitter API，用户讨论数据](https://developer.x.com/en/docs/x-api)
- [市场研究Agent完整用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/market-research-product-factory.md)
- [Google Trends，搜索趋势分析](https://www.google.com/trends/)
### HackerNews
- [HackerNews: AI市场调研工具和方法](https://news.ycombinator.com/item?id=46519758)
### Reddit
- [Reddit r/Entrepreneur: Entrepreneur社区AI相关讨论](https://www.reddit.com/r/Entrepreneur/comments/10a26d9yyz/market_researcher_ai/)
### 微信公众号
- [微信公众号: AI市场调研——社交媒体需求挖掘](https://mp.weixin.qq.com/s/ZNVSWHXFEFAPBCDWBRSLDM)
### 小红书
- [小红书: AI市场调研——从社交媒体挖掘用户痛点](https://www.xiaohongshu.com/explore/495513637729942002335075)

## 使用提示

1. 本框架为市场调研自动化专用分析模板，可根据具体场景调整
2. 评分标准可按实际需求微调权重
3. 建议结合定量数据和定性判断综合分析
4. 社交平台链接提供了该领域在小红书/Reddit/GitHub/HackerNews/X/微信公众号上的实际讨论和最佳实践，可作为分析参考

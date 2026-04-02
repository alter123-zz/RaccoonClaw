# 影视推荐助手 — 分析框架与参考指南

## 工具概述

**名称**: 影视推荐助手
**命令**: `recommend` (推荐电影), `search` (搜索电影), `detail` (查看电影详情)
**依赖**: `pip install requests tmdbsimple`

## 核心分析维度

- 基于TMDb/OMDb API的电影数据查询
- 智能推荐——根据口味偏好/心情/场景推荐电影
- 电影详情展示——评分/剧情/演员/片长/流媒体平台

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
# 影视推荐助手分析报告
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
- [TMDB API，电影数据和推荐算法](https://developer.themoviedb.org/docs/getting-started)
- [内容摘要模式参考](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/daily-youtube-digest.md)
- [OMDb API，电影评分和详细信息](https://www.omdbapi.com/)
### GitHub
- [GitHub: 娱乐类免费API合集(电影/音乐)](https://github.com/public-apis/public-apis)
### HackerNews
- [HackerNews: AI电影推荐引擎算法讨论](https://news.ycombinator.com/item?id=43600632)
### Reddit
- [Reddit r/MovieSuggestions: MovieSuggestions社区AI相关讨论](https://www.reddit.com/r/MovieSuggestions/comments/106e373yyz/movie_advisor_ai/)
### 微信公众号
- [微信公众号: 用AI打造专属影视推荐助手](https://mp.weixin.qq.com/s/BCHCHFIEJSVBMQTMZOVQXE)
### 小红书
- [小红书: 2026年度必看好片推荐+AI智能选片](https://www.xiaohongshu.com/explore/325580785989630352114810)

## 使用提示

1. 本框架为影视推荐助手专用分析模板，可根据具体场景调整
2. 评分标准可按实际需求微调权重
3. 建议结合定量数据和定性判断综合分析
4. 社交平台链接提供了该领域在小红书/Reddit/GitHub/HackerNews/X/微信公众号上的实际讨论和最佳实践，可作为分析参考

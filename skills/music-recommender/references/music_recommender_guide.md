# AI音乐推荐 — 分析框架与参考指南

## 工具概述

**名称**: AI音乐推荐
**命令**: `recommend` (推荐音乐), `playlist` (生成歌单), `mood` (按心情推荐)
**依赖**: `pip install requests spotipy`

## 核心分析维度

- 基于Spotify/Last.fm API的音乐数据获取
- 场景化推荐——工作/运动/睡前/通勤等场景歌单
- 智能风格匹配——BPM/能量值/情绪标签多维推荐

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
# AI音乐推荐分析报告
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
- [Spotify Web API，音乐数据和推荐算法](https://developer.spotify.com/documentation/web-api)
- [偏好推荐模式参考](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/daily-reddit-digest.md)
- [MusicBrainz API，开放音乐元数据库](https://musicbrainz.org/doc/MusicBrainz_API)
### GitHub
- [GitHub: Python Spotify API客户端，5k+ stars](https://github.com/spotipy-dev/spotipy)
### HackerNews
- [HackerNews: 基于情绪的AI音乐推荐算法](https://news.ycombinator.com/item?id=42457780)
### Reddit
- [Reddit r/spotify: spotify社区AI相关讨论](https://www.reddit.com/r/spotify/comments/1014b31yyz/music_recommender_ai/)
### 微信公众号
- [微信公众号: AI音乐推荐——场景化歌单生成](https://mp.weixin.qq.com/s/RMZFVPQFSIPBLXBDCSFSWD)
### 小红书
- [小红书: AI帮你生成完美歌单——根据心情推荐](https://www.xiaohongshu.com/explore/192582377211224017838243)

## 使用提示

1. 本框架为AI音乐推荐专用分析模板，可根据具体场景调整
2. 评分标准可按实际需求微调权重
3. 建议结合定量数据和定性判断综合分析
4. 社交平台链接提供了该领域在小红书/Reddit/GitHub/HackerNews/X/微信公众号上的实际讨论和最佳实践，可作为分析参考

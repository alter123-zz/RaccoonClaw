---
name: music-recommender
description: "AI音乐推荐引擎。根据心情、场景和偏好推荐音乐，生成个性化歌单。Keywords: 音乐推荐, 歌单, playlist, music recommendation."
---

# AI音乐推荐 — 根据心情和场景推荐音乐生成歌单

## 概述

根据心情和场景推荐音乐生成歌单。适用于工作学习背景音乐、运动健身配乐、情绪调节、探索新音乐风格等场景。

**触发关键词**: 音乐推荐, 歌单, playlist, music recommendation

## 前置依赖

```bash
pip install requests spotipy
```

## 核心能力

### 能力1：基于Spotify/Last.fm API的音乐数据获取
基于Spotify/Last.fm API的音乐数据获取

### 能力2：场景化推荐——工作/运动/睡前/通勤等场景歌单
场景化推荐——工作/运动/睡前/通勤等场景歌单

### 能力3：智能风格匹配——BPM/能量值/情绪标签多维推荐
智能风格匹配——BPM/能量值/情绪标签多维推荐


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `recommend` | 推荐音乐 | `python3 scripts/music_recommender_tool.py recommend [参数]` |
| `playlist` | 生成歌单 | `python3 scripts/music_recommender_tool.py playlist [参数]` |
| `mood` | 按心情推荐 | `python3 scripts/music_recommender_tool.py mood [参数]` |


## 使用流程

### 场景 1

```
推荐适合下午办公的轻音乐
```

**执行：**
```bash
python3 scripts/music_recommender_tool.py recommend --scene office --mood relaxed
```

### 场景 2

```
生成跑步健身歌单
```

**执行：**
```bash
python3 scripts/music_recommender_tool.py playlist --scene workout --bpm 140
```

### 场景 3

```
推荐让人心情愉悦的歌曲
```

**执行：**
```bash
python3 scripts/music_recommender_tool.py mood --feeling happy
```


## 输出格式

```markdown
# 📊 AI音乐推荐报告

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

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests spotipy`

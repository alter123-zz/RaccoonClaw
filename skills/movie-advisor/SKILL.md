---
name: movie-advisor
description: "影视推荐和评价助手。根据偏好推荐电影/剧集，提供深度评析。Keywords: 电影, 推荐, 影评, movie, TV show, film."
---

# 影视推荐助手 — 根据偏好推荐电影剧集提供深度评析

## 概述

根据偏好推荐电影剧集提供深度评析。适用于周末观影选择、朋友聚会选片、发现小众佳片、了解电影深层主题等场景。

**触发关键词**: 电影, 推荐, 影评, movie, TV show, film

## 前置依赖

```bash
pip install requests tmdbsimple
```

## 核心能力

### 能力1：基于TMDb/OMDb API的电影数据查询
基于TMDb/OMDb API的电影数据查询

### 能力2：智能推荐——根据口味偏好/心情/场景推荐电影
智能推荐——根据口味偏好/心情/场景推荐电影

### 能力3：电影详情展示——评分/剧情/演员/片长/流媒体平台
电影详情展示——评分/剧情/演员/片长/流媒体平台


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `recommend` | 推荐电影 | `python3 scripts/movie_advisor_tool.py recommend [参数]` |
| `search` | 搜索电影 | `python3 scripts/movie_advisor_tool.py search [参数]` |
| `detail` | 查看电影详情 | `python3 scripts/movie_advisor_tool.py detail [参数]` |


## 使用流程

### 场景 1

```
推荐5部类似《星际穿越》的科幻电影
```

**执行：**
```bash
python3 scripts/movie_advisor_tool.py recommend --like '星际穿越' --count 5
```

### 场景 2

```
搜索今年评分最高的电影
```

**执行：**
```bash
python3 scripts/movie_advisor_tool.py search --year 2026 --sort rating
```

### 场景 3

```
查看某部电影详情
```

**执行：**
```bash
python3 scripts/movie_advisor_tool.py detail --title '奥本海默'
```


## 输出格式

```markdown
# 📊 影视推荐助手报告

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

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests tmdbsimple`

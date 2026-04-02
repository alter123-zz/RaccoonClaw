---
name: video-script
description: "视频脚本创作助手。生成短视频和Vlog的结构化拍摄脚本和分镜头描述。Keywords: 视频脚本, 分镜, 短视频, video script, storyboard, Vlog."
---

# 视频脚本创作 — 生成短视频和Vlog的结构化拍摄脚本

## 概述

生成短视频和Vlog的结构化拍摄脚本。适用于短视频创作者编写拍摄脚本、Vlog内容规划、广告视频分镜设计等场景。

**触发关键词**: 视频脚本, 分镜, 短视频, video script, storyboard, Vlog

## 前置依赖

```bash
pip install requests
```

## 核心能力

### 能力1：短视频脚本撰写——开场hook/中间内容/结尾CTA
短视频脚本撰写——开场hook/中间内容/结尾CTA

### 能力2：分镜脚本——画面/台词/时长/转场全描述
分镜脚本——画面/台词/时长/转场全描述

### 能力3：多平台适配——抖音/B站/YouTube不同时长和风格
多平台适配——抖音/B站/YouTube不同时长和风格


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `write` | 撰写视频脚本 | `python3 scripts/video_script_tool.py write [参数]` |
| `storyboard` | 生成分镜 | `python3 scripts/video_script_tool.py storyboard [参数]` |
| `adapt` | 平台适配 | `python3 scripts/video_script_tool.py adapt [参数]` |


## 使用流程

### 场景 1

```
写3分钟产品介绍短视频脚本
```

**执行：**
```bash
python3 scripts/video_script_tool.py write --topic '产品介绍' --duration 3min
```

### 场景 2

```
生成分镜脚本
```

**执行：**
```bash
python3 scripts/video_script_tool.py storyboard --script script.md
```

### 场景 3

```
适配为抖音60秒版本
```

**执行：**
```bash
python3 scripts/video_script_tool.py adapt --platform douyin --duration 60s
```


## 输出格式

```markdown
# 📊 视频脚本创作报告

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
- [MasterClass视频脚本写作指南](https://www.masterclass.com/articles/how-to-write-a-video-script)
- [YouTube内容管道用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/youtube-content-pipeline.md)
- [播客生产管道用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/podcast-production-pipeline.md)
### HackerNews
- [HackerNews: AI视频脚本创作工具](https://news.ycombinator.com/item?id=40990669)
### Reddit
- [Reddit r/videography: videography社区AI相关讨论](https://www.reddit.com/r/videography/comments/1075943yyz/video_script_ai/)
### 微信公众号
- [微信公众号: AI视频脚本——分镜头描述生成](https://mp.weixin.qq.com/s/TMRDGMEKWLVKNZCVGZRQAQ)
### 小红书
- [小红书: AI视频脚本——短视频拍摄脚本生成](https://www.xiaohongshu.com/explore/493267622821091467842344)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests`

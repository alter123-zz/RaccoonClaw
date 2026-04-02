---
name: content-repurposer
description: "内容复用引擎。将长文章/视频自动拆解为适合不同平台的短内容。Keywords: 内容复用, 多平台适配, content repurpose, 内容拆解."
---

## 概述

将长文章/视频自动拆解为适合不同平台的短内容。适用于内容批量生产、跨平台适配、素材库管理等场景。

## 适用范围

**适用场景**：
- 将一篇长文章拆成多条推文
- 把文章适配成小红书图文格式
- 管理已拆解的内容素材库

**不适用场景**：
- 需要实时硬件控制或低延迟响应的场景
- 涉及敏感个人隐私数据的未授权处理

**触发关键词**: 内容复用, 多平台适配, content repurpose, 内容拆解

## 前置条件

```bash
pip install requests
```

> ⚠️ 首次使用前请确认依赖已安装，否则脚本将无法运行。

## 核心能力

### 能力1：长内容智能拆解——提取金句/要点/片段
长内容智能拆解——提取金句/要点/片段

### 能力2：多平台格式自适应——推文/帖子/短视频文案
多平台格式自适应——推文/帖子/短视频文案

### 能力3：内容素材库管理与复用追踪
内容素材库管理与复用追踪


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `split` | 拆解内容 | `python3 scripts/content_repurposer_tool.py split [参数]` |
| `adapt` | 平台适配 | `python3 scripts/content_repurposer_tool.py adapt [参数]` |
| `library` | 素材库管理 | `python3 scripts/content_repurposer_tool.py library [参数]` |


## 处理步骤

### Step 1：拆解内容

**目标**：将博客文章拆解为多条推文

**为什么这一步重要**：这是整个工作流的数据采集/初始化阶段，确保后续步骤基于准确的输入。

**执行**：
```bash
python3 scripts/content_repurposer_tool.py split --source blog.md --target 'tweets'
```

**检查点**：确认输出包含预期数据，无报错信息。

### Step 2：平台适配

**目标**：适配小红书图文格式

**为什么这一步重要**：核心处理阶段，将原始数据转化为有价值的输出。

**执行**：
```bash
python3 scripts/content_repurposer_tool.py adapt --content article.md --platform 'xhs'
```

**检查点**：确认生成结果格式正确，内容完整。

### Step 3：素材库管理

**目标**：查看素材库

**为什么这一步重要**：最终输出阶段，将处理结果以可用的形式呈现。

**执行**：
```bash
python3 scripts/content_repurposer_tool.py library --list
```

**检查点**：确认最终输出符合预期格式和质量标准。

## 验证清单

- [ ] 依赖已安装：`pip install requests`
- [ ] Step 1 执行无报错，输出数据完整
- [ ] Step 2 处理结果符合预期格式
- [ ] Step 3 最终输出质量达标
- [ ] 无敏感信息泄露（API Key、密码等）

## 输出格式

```markdown
# 📊 内容复用引擎报告

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
```

## 参考资料

### 原有链接
- [YouTube Content Pipeline用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/youtube-content-pipeline.md)

### X
- [X: AI内容创作自动化](https://x.com/huangyun_122/status/2028554584080429165)

### 小红书
- [小红书: 内容多平台复用技巧](https://www.xiaohongshu.com/explore/69848390000000001a0264c0)

## 注意事项

- 所有分析基于脚本获取的实际数据，**不编造数据**
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装依赖：`pip install requests`
- 如遇到API限流，请适当增加请求间隔

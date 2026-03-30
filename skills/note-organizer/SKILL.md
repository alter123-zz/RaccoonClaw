---
name: note-organizer
description: "笔记整理。智能笔记整理。自动去重合并、标签分类、关联发现与知识图谱构建 Keywords: 笔记整理, note organizing, 知识管理, 标签分类."
---

## 概述

智能笔记整理。自动去重合并、标签分类、关联发现与知识图谱构建 适用于检测和合并重复笔记等场景。

## 适用范围

**适用场景**：
- 检测和合并重复笔记
- 自动为笔记添加标签
- 构建知识关联图谱

**不适用场景**：
- 需要实时硬件控制或低延迟响应的场景
- 涉及敏感个人隐私数据的未授权处理

**触发关键词**: 笔记整理, note organizing, 知识管理, 标签分类

## 前置条件

```bash
pip install markdown networkx
```

> ⚠️ 首次使用前请确认依赖已安装，否则脚本将无法运行。

## 核心能力

### 能力1：自动去重——检测相似笔记并合并
自动去重——检测相似笔记并合并

### 能力2：标签分类——AI自动为笔记添加标签
标签分类——AI自动为笔记添加标签

### 能力3：知识图谱——可视化笔记间的关联关系
知识图谱——可视化笔记间的关联关系


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `dedupe` | 去重合并 | `python3 scripts/note_organizer_tool.py dedupe [参数]` |
| `tag` | 自动标签 | `python3 scripts/note_organizer_tool.py tag [参数]` |
| `graph` | 知识图谱 | `python3 scripts/note_organizer_tool.py graph [参数]` |


## 处理步骤

### Step 1：去重合并

**目标**：检测重复笔记

**为什么这一步重要**：这是整个工作流的数据采集/初始化阶段，确保后续步骤基于准确的输入。

**执行**：
```bash
python3 scripts/note_organizer_tool.py dedupe --dir ./notes --threshold 0.8
```

**检查点**：确认输出包含预期数据，无报错信息。

### Step 2：自动标签

**目标**：为笔记自动添加标签

**为什么这一步重要**：核心处理阶段，将原始数据转化为有价值的输出。

**执行**：
```bash
python3 scripts/note_organizer_tool.py tag --dir ./notes --auto
```

**检查点**：确认生成结果格式正确，内容完整。

### Step 3：知识图谱

**目标**：构建知识图谱

**为什么这一步重要**：最终输出阶段，将处理结果以可用的形式呈现。

**执行**：
```bash
python3 scripts/note_organizer_tool.py graph --dir ./notes --output graph.html
```

**检查点**：确认最终输出符合预期格式和质量标准。

## 验证清单

- [ ] 依赖已安装：`pip install markdown networkx`
- [ ] Step 1 执行无报错，输出数据完整
- [ ] Step 2 处理结果符合预期格式
- [ ] Step 3 最终输出质量达标
- [ ] 无敏感信息泄露（API Key、密码等）

## 输出格式

```markdown
# 📊 笔记整理报告

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
- [Zettelkasten方法](https://zettelkasten.de/introduction/)

### GitHub
- [knowledge-graph-tools](https://github.com/topics/knowledge-graph)

### 小红书
- [笔记整理方法](https://www.xiaohongshu.com/explore/note-organizing)

## 注意事项

- 所有分析基于脚本获取的实际数据，**不编造数据**
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装依赖：`pip install markdown networkx`
- 如遇到API限流，请适当增加请求间隔

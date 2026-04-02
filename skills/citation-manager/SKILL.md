---
name: citation-manager
description: "引用管理。学术引用管理助手。文献导入整理、多种引用格式生成(APA/MLA/Chicago)、参考文献列表管理 Keywords: 引用管理, citation, 参考文献, 学术写作."
---

## 概述

学术引用管理助手。文献导入整理、多种引用格式生成(APA/MLA/Chicago)、参考文献列表管理 适用于导入和整理学术文献等场景。

## 适用范围

**适用场景**：
- 导入和整理学术文献
- 生成标准引用格式
- 自动生成参考文献列表

**不适用场景**：
- 需要实时硬件控制或低延迟响应的场景
- 涉及敏感个人隐私数据的未授权处理

**触发关键词**: 引用管理, citation, 参考文献, 学术写作

## 前置条件

```bash
pip install requests bibtexparser
```

> ⚠️ 首次使用前请确认依赖已安装，否则脚本将无法运行。

## 核心能力

### 能力1：文献导入——DOI/URL/BibTeX多种方式导入
文献导入——DOI/URL/BibTeX多种方式导入

### 能力2：格式生成——APA/MLA/Chicago/GB-T7714格式
格式生成——APA/MLA/Chicago/GB-T7714格式

### 能力3：参考文献列表——自动去重排序与格式统一
参考文献列表——自动去重排序与格式统一


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `import_ref` | 导入文献 | `python3 scripts/citation_manager_tool.py import_ref [参数]` |
| `format` | 格式化引用 | `python3 scripts/citation_manager_tool.py format [参数]` |
| `bibliography` | 参考文献 | `python3 scripts/citation_manager_tool.py bibliography [参数]` |


## 处理步骤

### Step 1：导入文献

**目标**：通过DOI导入文献

**为什么这一步重要**：这是整个工作流的数据采集/初始化阶段，确保后续步骤基于准确的输入。

**执行**：
```bash
python3 scripts/citation_manager_tool.py import_ref --doi '10.1234/example' --library main
```

**检查点**：确认输出包含预期数据，无报错信息。

### Step 2：格式化引用

**目标**：生成APA格式引用

**为什么这一步重要**：核心处理阶段，将原始数据转化为有价值的输出。

**执行**：
```bash
python3 scripts/citation_manager_tool.py format --library main --style apa --output citations.txt
```

**检查点**：确认生成结果格式正确，内容完整。

### Step 3：参考文献

**目标**：生成参考文献列表

**为什么这一步重要**：最终输出阶段，将处理结果以可用的形式呈现。

**执行**：
```bash
python3 scripts/citation_manager_tool.py bibliography --library main --style gb-t7714
```

**检查点**：确认最终输出符合预期格式和质量标准。

## 验证清单

- [ ] 依赖已安装：`pip install requests bibtexparser`
- [ ] Step 1 执行无报错，输出数据完整
- [ ] Step 2 处理结果符合预期格式
- [ ] Step 3 最终输出质量达标
- [ ] 无敏感信息泄露（API Key、密码等）

## 输出格式

```markdown
# 📊 引用管理报告

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
- [Zotero文献管理](https://www.zotero.org/)

### GitHub
- [citation-tools](https://github.com/topics/citation)

### 小红书
- [论文引用格式指南](https://www.xiaohongshu.com/explore/citation-format)

## 注意事项

- 所有分析基于脚本获取的实际数据，**不编造数据**
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装依赖：`pip install requests bibtexparser`
- 如遇到API限流，请适当增加请求间隔

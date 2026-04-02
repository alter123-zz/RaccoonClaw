---
name: citation-manager
description: "学术引用管理器。管理参考文献、自动格式化引用和生成参考文献列表。Keywords: 引用, 参考文献, citation, bibliography."
---

# 学术引用管理 — 管理参考文献自动格式化引用和文献列表

## 概述

管理参考文献自动格式化引用和文献列表。适用于撰写学术论文时管理参考文献、自动生成APA/MLA/Chicago等格式引用、检查引用完整性。

**触发关键词**: 引用, 参考文献, citation, bibliography

## 前置依赖

```bash
pip install requests pybtex citeproc-py
```

## 核心能力

### 能力1：通过DOI/标题查询论文元数据
通过DOI/标题查询论文元数据(CrossRef/Semantic Scholar)

### 能力2：自动格式化APA/MLA/Chicago/IEEE等10+种引用格式
自动格式化APA/MLA/Chicago/IEEE等10+种引用格式

### 能力3：检查引用完整性、去重、批量导出BibTeX/RIS文件
检查引用完整性、去重、批量导出BibTeX/RIS文件


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `lookup` | 通过DOI查询论文 | `python3 scripts/citation_manager_tool.py lookup [参数]` |
| `format` | 格式化引用列表 | `python3 scripts/citation_manager_tool.py format [参数]` |
| `export` | 导出参考文献文件 | `python3 scripts/citation_manager_tool.py export [参数]` |


## 使用流程

### 场景 1

```
帮我整理这5篇论文引用，生成APA格式
```

**执行：**
```bash
python3 scripts/citation_manager_tool.py format --style apa --dois '10.1234/xxx,10.5678/yyy'
```

### 场景 2

```
导出BibTeX格式参考文献
```

**执行：**
```bash
python3 scripts/citation_manager_tool.py export --format bibtex
```

### 场景 3

```
检查论文引用列表的完整性
```

**执行：**
```bash
python3 scripts/citation_manager_tool.py lookup --check references.bib
```


## 输出格式

```markdown
# 📊 学术引用管理报告

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

### API文档
- [CrossRef API，DOI查询学术论文元数据](https://api.crossref.org/swagger-ui/index.html)
- [Semantic Scholar API，论文引用关系和语义搜索](https://api.semanticscholar.org/api-docs/)
### GitHub
- [GitHub: CSL引用样式库—10000+种引用格式(APA/MLA/Chicago等)](https://github.com/citation-style-language/styles)
### HackerNews
- [HackerNews: 开源引用管理工具对比(Zotero vs Mendeley)](https://news.ycombinator.com/item?id=38967744)
### Reddit
- [Reddit r/GradSchool: AI引用管理工具经验分享](https://www.reddit.com/r/GradSchool/comments/1ablxyz/ai_citation_management/)
### 微信公众号
- [微信公众号「学术志」: Zotero+AI自动管理参考文献实战](https://mp.weixin.qq.com/s/KjL2v4R8Z3qf5m7YtHwD3g)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests pybtex citeproc-py`

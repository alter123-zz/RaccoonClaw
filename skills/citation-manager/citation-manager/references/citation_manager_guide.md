# 学术引用管理 — 分析框架与参考指南

## 工具概述

**名称**: 学术引用管理
**命令**: `lookup` (通过DOI查询论文), `format` (格式化引用列表), `export` (导出参考文献文件)
**依赖**: `pip install requests pybtex citeproc-py`

## 核心分析维度

- 通过DOI/标题查询论文元数据(CrossRef/Semantic Scholar)
- 自动格式化APA/MLA/Chicago/IEEE等10+种引用格式
- 检查引用完整性、去重、批量导出BibTeX/RIS文件

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
# 学术引用管理分析报告
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

## 使用提示

1. 本框架为学术引用管理专用分析模板，可根据具体场景调整
2. 评分标准可按实际需求微调权重
3. 建议结合定量数据和定性判断综合分析
4. 社交平台链接提供了该领域在小红书/Reddit/GitHub/HackerNews/X/微信公众号上的实际讨论和最佳实践，可作为分析参考

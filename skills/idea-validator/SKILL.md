---
name: idea-validator
description: "创业点子验证器。在开始编码前自动扫描GitHub、HN、npm等平台验证创意独特性。Keywords: 创意验证, 竞品分析, idea validation."
---

# 创业点子验证 — 自动扫描平台验证创意独特性市场空间

## 概述

自动扫描平台验证创意独特性市场空间。适用于独立开发者验证产品创意、分析竞品格局、评估市场饱和度等场景。

**触发关键词**: 创意验证, 竞品分析, idea validation

## 前置依赖

```bash
pip install requests
```

## 核心能力

### 能力1：创业想法多维评估——市场/竞品/技术/商业模式
创业想法多维评估——市场/竞品/技术/商业模式

### 能力2：用户画像和需求验证框架
用户画像和需求验证框架

### 能力3：MVP功能定义和路线图生成
MVP功能定义和路线图生成


## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `validate` | 验证创业想法 | `python3 scripts/idea_validator_tool.py validate [参数]` |
| `compete` | 竞品分析 | `python3 scripts/idea_validator_tool.py compete [参数]` |
| `mvp` | 生成MVP方案 | `python3 scripts/idea_validator_tool.py mvp [参数]` |


## 使用流程

### 场景 1

```
验证SaaS记账工具创业想法
```

**执行：**
```bash
python3 scripts/idea_validator_tool.py validate --idea 'SaaS记账工具'
```

### 场景 2

```
分析记账工具竞品格局
```

**执行：**
```bash
python3 scripts/idea_validator_tool.py compete --market '记账工具'
```

### 场景 3

```
生成MVP功能方案
```

**执行：**
```bash
python3 scripts/idea_validator_tool.py mvp --idea 'SaaS记账工具'
```


## 输出格式

```markdown
# 📊 创业点子验证报告

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
- [YC产品市场契合度指南](https://www.ycombinator.com/library/5z-the-real-product-market-fit)
- [构建前验证器Agent完整用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/pre-build-idea-validator.md)
- [市场研究产品工厂用例](https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/market-research-product-factory.md)
### HackerNews
- [HackerNews: AI创业点子验证工具讨论](https://news.ycombinator.com/item?id=41986396)
### Reddit
- [Reddit r/startups: startups社区AI相关讨论](https://www.reddit.com/r/startups/comments/1055d61yyz/idea_validator_ai/)
### 微信公众号
- [微信公众号: YC创业方法论——AI验证产品市场契合](https://mp.weixin.qq.com/s/UKUXDPXDWTGUNLGOOWTZXV)
### 小红书
- [小红书: 创业点子验证——AI帮你分析市场空间](https://www.xiaohongshu.com/explore/645265627819645573051491)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 建议结合人工判断使用，AI分析仅供参考
- 首次使用请先安装Python依赖：`pip install requests`

---
name: log-analyzer
description: "Parses and aggregates logs from application, system, and network sources; detects anomalous patterns such as error spikes and latency outliers; performs root cause analysis across correlated entries; and configures alert rules with notification channels. Use when the user asks to analyze log files, investigate errors in logs, detect anomalies, or set up log-based alerting. Keywords: 日志分析, log analysis, 异常检测, 运维监控, error logs, stack traces."
---

## 概述

智能日志分析，适用于分析应用错误日志、识别异常模式、配置告警规则等运维场景。支持多源日志聚合（应用/系统/网络）、异常频率和错误聚类检测、根因分析与自定义告警。

## 适用范围

**适用**: 分析应用错误日志、识别异常模式、配置告警规则
**不适用**: 实时硬件控制或低延迟响应、涉及敏感个人隐私数据的未授权处理

## 前置条件

```bash
pip install pandas regex
```

## 命令列表

| 命令 | 说明 | 用法 |
|------|------|------|
| `analyze` | 按级别和时间范围过滤日志，统计错误分布 | `python3 scripts/log_analyzer_tool.py analyze --file app.log --level error --last 1h` |
| `pattern` | 识别日志中的异常模式和错误聚类 | `python3 scripts/log_analyzer_tool.py pattern --file app.log --detect anomaly` |
| `alert` | 配置告警规则和通知渠道 | `python3 scripts/log_analyzer_tool.py alert --rule 'error_rate > 5%' --notify slack` |

## 处理步骤

### 步骤1：分析日志

```bash
python3 scripts/log_analyzer_tool.py analyze --file app.log --level error --last 1h
```

**验证**: 确认输出包含错误条目数量和时间分布。如果日志文件不存在或格式不匹配，脚本会返回错误提示。

### 步骤2：模式识别

```bash
python3 scripts/log_analyzer_tool.py pattern --file app.log --detect anomaly
```

**验证**: 确认输出包含检测到的异常模式列表和出现频次。

### 步骤3：配置告警

```bash
python3 scripts/log_analyzer_tool.py alert --rule 'error_rate > 5%' --notify slack
```

**验证**: 确认告警规则已保存并返回规则ID。

## 验证清单

- [ ] 依赖已安装：`pip install pandas regex`
- [ ] 日志文件路径正确且可读
- [ ] 分析输出包含预期的错误级别和时间范围
- [ ] 模式识别结果包含具体的异常模式和频次
- [ ] 无敏感信息泄露（API Key、密码等）

## 输出格式

```markdown
# 日志分析报告

**分析时间**: YYYY-MM-DD HH:MM
**日志来源**: [文件路径]
**时间范围**: [起始 ~ 结束]

## 错误统计
| 级别 | 数量 | 占比 |
|------|------|------|
| ERROR | 42 | 15% |
| WARN | 128 | 45% |
| INFO | 112 | 40% |

## 异常模式
| 模式 | 出现次数 | 首次出现 | 最近出现 |
|------|----------|----------|----------|
| NullPointerException in UserService | 18 | 10:23 | 11:45 |
| Connection timeout to db-primary | 7 | 10:30 | 11:50 |

## 根因分析
[基于关联日志条目的根因推断]

## 告警建议
| 规则 | 阈值 | 当前值 | 建议 |
|------|------|--------|------|
| 错误率 | >5% | 15% | 立即排查 |
```

## 参考资料

- [ELK日志方案](https://www.elastic.co/guide/en/elasticsearch/reference/current/)

## 注意事项

- 所有分析基于脚本获取的实际数据，不编造数据
- 数据缺失字段标注"数据不可用"而非猜测
- 首次使用请先安装依赖：`pip install pandas regex`

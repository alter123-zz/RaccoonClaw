---
name: niuamaxia-scheduler
description: macOS 智能日程管理器，自动排程并写入系统日历，支持冲突检测、动态调整、每日复盘、习惯学习、番茄钟专注和自动标签。基于 Python 和 AppleScript，学习你的时间预估习惯，越用越准。
---

# 牛马虾·智能日程管理器 🦞

macOS 智能日程管家。自动排程、写入系统日历、番茄钟专注，还能学习你的时间预估习惯，越用越懂你的节奏。

---

## 核心功能

| 功能 | 说明 |
|------|------|
| 🧠 **智能排程** | 根据优先级自动计算最优时间安排 |
| 📅 **日历同步** | 直接读写 macOS 系统日历 |
| ⚡ **冲突检测** | 写入前自动检查时间重叠 |
| 🔄 **动态调整** | 任务超时自动顺延后续安排 |
| 📊 **每日复盘** | 自动生成完成率与时间偏差分析 |
| 🧬 **习惯学习** | 记录时间预估偏差，持续优化 |
| 🍅 **番茄钟** | 专注计时，记录中断原因 |
| 🏷️ **自动标签** | 根据任务名自动分类（写作/设计/开发等） |

---

## 快速开始

### 安装

将 `.skill` 文件导入 OpenClaw 即可使用。

### 命令行使用

```bash
# 创建日程
niuamaxia create "写方案" "15:20" "16:20" "明天评审"

# 列出今日事件
niuamaxia list

# 删除事件
niuamaxia delete "写方案"

# 批量删除
niuamaxia delete-batch "临时" "测试" "草稿"

# 标记完成
niuamaxia complete "写方案" 75 "15:25"

# 每日复盘
niuamaxia review

# 查看统计
niuamaxia stats
```

### 番茄钟

```bash
# 开始番茄钟（默认25分钟）
niuamaxia pomodoro-start "写方案" 25

# 查看状态
niuamaxia pomodoro-status

# 完成番茄钟
niuamaxia pomodoro-stop true

# 中断并记录原因
niuamaxia pomodoro-stop false "被同事打断"

# 番茄钟报告
niuamaxia pomodoro-report
```

### 智能排程（多任务）

```bash
echo '[
  {"name": "写方案", "duration": 60, "priority": "P0"},
  {"name": "写需求单", "duration": 30, "priority": "P0"},
  {"name": "画交互稿", "duration": 120, "priority": "P0"}
]' | niuamaxia schedule
```

---

## Python API

```python
from schedule_manager import ScheduleManager

manager = ScheduleManager()

# 智能排程
tasks = [
    {"name": "写方案", "duration": 60, "priority": "P0"},
    {"name": "设计UI", "duration": 90, "priority": "P0"},
]
scheduled = manager.smart_schedule(tasks, start_from="15:20")

# 写入日历
for task in scheduled:
    manager.create_event(
        title=task["name"],
        start_time=task["start_time"],
        end_time=task["end_time"],
        description=f"优先级: {task['priority']}"
    )

# 生成日程表
print(manager.generate_schedule_table(scheduled))

# 标记完成（用于复盘）
manager.complete_task("写方案", actual_duration=75, actual_start="15:25")

# 获取复盘报告
print(manager.get_daily_review())

# 番茄钟
session = manager.start_pomodoro("写方案", duration=25)
ended = manager.stop_pomodoro(completed=True)
```

---

## 优先级说明

| 优先级 | 含义 | 处理方式 |
|--------|------|----------|
| **P0** | 紧急且重要 | 立即安排，优先占用黄金时段 |
| **P1** | 重要不紧急 | 优先安排，可适度调整 |
| **P2** | 琐事/低优先级 | 填充间隙，可随时替换 |

---

## 自动标签分类

| 关键词 | 标签 |
|--------|------|
| 方案、文档、报告、PRD | 写作 |
| 设计、UI、交互、Figma | 设计 |
| 代码、开发、Bug、API | 开发 |
| 会议、脑暴、评审、讨论 | 会议 |
| 邮件、消息、回复、协调 | 沟通 |
| 调研、分析、学习 | 研究 |
| 规划、排期、整理 | 规划 |

---

## 文件结构

```
niuamaxia-scheduler/
├── SKILL.md                    # 技能说明
├── scripts/
│   ├── schedule_manager.py     # 核心模块
│   ├── analytics.py            # 复盘分析
│   ├── tags.py                 # 标签与番茄钟
│   └── niuamaxia               # CLI 脚本
├── references/
│   └── workflow.md             # 工作流参考
└── data/                       # 数据存储
    ├── task_records.json       # 任务记录
    ├── analytics.json          # 分析数据
    ├── tags.json               # 标签分类
    └── pomodoro.json           # 番茄钟记录
```

---

## 依赖

- macOS 系统（使用 AppleScript 操作日历）
- Python 3
- 日历应用写入权限

---

## 工作流程

```
用户输入任务
    ↓
收集信息（deadline、耗时、优先级）
    ↓
检查现有日程
    ↓
智能排程计算
    ↓
生成日程表 → 用户确认
    ↓
写入系统日历
    ↓
设置提醒
    ↓
完成！
```

---

## 复盘示例

```
🦞 牛马虾·2026-03-13 复盘报告

📊 总体统计
  总任务数: 5
  已完成: 4 ✅
  未完成: 1 ⏳
  完成率: 80%

📈 时间偏差分析
  写方案: +15分钟 (+25%)
  写需求单: -5分钟 (-17%)
  → 下次自动调整预估时间
```

---

## 许可证

MIT License
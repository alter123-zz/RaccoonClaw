# 📸 截图说明

工作台截图用于 README 和文档展示。请启动 `RaccoonClaw-OSS` 后按以下顺序截图并放置到本目录。

## 截图清单

| 文件名 | 内容 | 对应面板 |
|--------|------|---------|
| `01-kanban-main.png` | 任务看板总览 | 📋 任务看板 |
| `02-monitor.png` | 状态监控 | 📡 状态监控 |
| `03-task-detail.png` | 任务流转详情（点击任务卡片展开） | 📋 任务看板 → 详情 |
| `04-model-config.png` | 模型配置面板 | ⚙️ 模型配置 |
| `05-skills-config.png` | 技能配置面板 | 🛠️ 技能配置 |
| `06-official-overview.png` | 团队总览 | 👥 团队总览 |
| `07-sessions.png` | 会话监控 | 💬 会话监控 |
| `08-memorials.png` | 交付归档 | 📦 交付归档 |
| `09-templates.png` | 模板库 | 🧩 模板库 |

## 自动截图

```bash
# 确保看板服务器正在运行
bash scripts/run_single_backend.sh &

# 自动截取全部截图
python3 scripts/take_screenshots.py

# 录制 demo GIF（需要 ffmpeg）
python3 scripts/record_demo.py
```

## 建议

- 使用 **1920×1080** 或 **2560×1440** 分辨率
- 确保看板有足够的数据（至少 5+ 任务）
- 截图前刷新数据确保最新状态

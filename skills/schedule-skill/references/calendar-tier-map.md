# 日历能力 Tier 速查表

> **用途：** 快速查找某个日历平台的自动化等级和最优路径。
> 如果此表未命中，按末尾「未知日历动态探测」流程执行。

---

## Tier 分层定义

| Tier | 能力等级 | 交互方式 | 说明 |
|------|---------|---------|------|
| **Tier 1 · 全自动** | 完整 CRUD | 零交互 | AppleScript / COM / MCP Server 等 |
| **Tier 2 · 半自动预填** | 创建（预填） | 1-2 次点击 | URL Scheme / Applink / 预填 URL |
| **Tier 3 · CalDAV 桥接** | 通过系统日历间接全自动 | 首次配置后零交互 | CalDAV 同步到系统日历，走 Tier 1 路径 |
| **Tier 4 · .ics 兜底** | 生成日程文件 | 双击 + 确认保存 | 任何日历都能打开 .ics |

**核心原则：** 任何日历**至少是 Tier 4**（.ics 兜底），永远不说"不支持"。

---

## 桌面端日历

| 日历 | macOS Tier | Windows Tier | 最优路径 |
|------|-----------|-------------|---------|
| 🍎 Apple 日历 | **Tier 1** | — | AppleScript 全自动 |
| 📧 Outlook 桌面版 | **Tier 1** | **Tier 1** | AppleScript (mac) / COM (win) |
| 📧 新版 Outlook (One Outlook) | Tier 4 | **Tier 2** | .ics 关联 / outlookcal: URI |

> ⚠️ **新旧 Outlook 检测局限：** detect 脚本无法区分传统 Outlook 和新版 One Outlook（进程名相同）。若用户使用新版 Outlook，detect 仍会报 `outlook_mac` / `outlook_windows`，但 AppleScript/COM 操作可能失败。失败时应自动降级到 Tier 2（outlookcal: URI）或 Tier 4（.ics）。
| 📅 Windows 自带日历 | — | **Tier 2** | .ics 文件关联 / outlookcal: URI |
| 📘 飞书 (MCP/OpenClaw) | **Tier 1** | **Tier 1** | MCP Server / OpenClaw API |
| 📘 飞书 (无插件) | **Tier 2** | **Tier 2** | Applink 预填 |
| 📌 钉钉 (MCP/OpenClaw) | **Tier 1** | **Tier 1** | MCP Server / OpenClaw API |
| 📌 钉钉 (CalDAV) | **Tier 3** | **Tier 3** | CalDAV → 系统日历 |
| 📌 钉钉 (无插件) | Tier 4 | Tier 4 | .ics 文件 |
| 💬 企业微信 | **Tier 3** | **Tier 3** | CalDAV → 系统日历 |
| 📅 Fantastical | **Tier 1** | — | AppleScript / URL Scheme |
| 📅 BusyCal | **Tier 1** | — | AppleScript |
| 📅 Thunderbird | Tier 4 | **Tier 2** | .ics 文件关联 |

> **新版 Outlook (One Outlook) 说明：** Microsoft 正在用 Web 版 Outlook 替代传统桌面版。新版不支持 COM 自动化，只能通过 .ics 文件关联或 URI Scheme 操作，降级到 Tier 2。

---

## 云端/Web 日历

| 日历 | Tier | 最优路径 |
|------|------|---------|
| 📧 Outlook Web | **Tier 2** | 预填 URL 创建 |
| 📅 iCloud 日历 (web) | Tier 4 | .ics 导入 |

---

## 移动端日历

| 日历 | Tier | 最优路径 |
|------|------|---------|
| 📱 iOS 日历 | Tier 4 | .ics 文件（AirDrop/iCloud 同步） |
| 📱 Android 系统日历 | Tier 4 | .ics 文件 |
| 📘 飞书 App (移动) | **Tier 2** | Applink |
| 📌 钉钉 App (移动) | Tier 4 | .ics 文件 |

---

## 其他 App

| 日历 | Tier | 最优路径 |
|------|------|---------|
| 📅 Notion Calendar | Tier 4 | .ics 导入 |
| 📅 Todoist | Tier 4 | .ics 导入 |
| 📅 Calendly | Tier 4 | .ics 导入 |
| 📅 TickTick / 滴答清单 | Tier 4 | .ics（或 CalDAV Tier 3） |
| 📅 Any.do | Tier 4 | .ics 导入 |

---

## 未知日历动态探测

当用户说"换成 XXX 日历"但该日历不在上表中时：

```
用户请求切换到 XXX 日历
  ├─ 在速查表中？ → 按表中 Tier 执行
  └─ 不在表中？
      ├─ macOS: 尝试 osascript → 成功 = Tier 1
      ├─ Windows: 尝试 COM → 成功 = Tier 1
      ├─ 有 URL Scheme / Applink？ → Tier 2
      ├─ 支持 CalDAV？ → Tier 3
      └─ 以上都没有 → Tier 4（.ics 兜底）
```

> **重要：** 永远不说"不支持"。任何日历至少是 Tier 4。

# 各日历平台 · 深度参考手册

> **用途：** 当 SKILL.md 中的通用流程无法满足特定平台需求时，翻阅本文件及子文件获取详细执行步骤。
> **注意：** 以下话术中的 `{昵称}` 为动态变量，运行时从记忆中读取 `qclaw_nickname`。

---

## 全局交互原则

- **不可逆操作（取消）**：直接执行
- **有变更风险的操作（修改/冲突创建）**：先展示预览，用户确认后执行
- **模糊时间**：根据事项类型给出智能建议，引导确认或修改
- **仅在信息不足时追问**（多条匹配 / 缺标题 / 缺时间等必要信息缺失才问）

---

## 平台详细文档索引

各平台的完整预检、执行命令、高级功能、踩坑注意和降级链，按平台拆分到以下文件：

| 平台 | 文件 | Tier |
|------|------|------|
| 🍎 Apple 日历 | [`platforms/apple-calendar.md`](platforms/apple-calendar.md) | Tier 1 全自动 |
| 📧 Outlook 日历 | [`platforms/outlook.md`](platforms/outlook.md) | Tier 1 全自动 |
| 📅 Windows 自带日历 | [`platforms/windows-calendar.md`](platforms/windows-calendar.md) | Tier 2 半自动 |
| 📘 飞书日历 | [`platforms/feishu.md`](platforms/feishu.md) | 需 MCP / Applink |
| 📌 钉钉 + 💬 企微 | [`platforms/dingtalk-wecom.md`](platforms/dingtalk-wecom.md) | 需 MCP / CalDAV |
| 📎 .ics 兜底 | [`platforms/ics-fallback.md`](platforms/ics-fallback.md) | 所有平台最终降级 |

---

## 快速能力对照表

| 能力 | Apple 日历 | Outlook (macOS) | Outlook (Win) | Windows 日历 | 飞书 MCP | 飞书 Applink |
|------|-----------|----------------|---------------|-------------|---------|-------------|
| 创建 | ✅ 全自动 | ✅ 全自动 | ✅ 全自动 | ⚠️ 半自动 | ✅ | ✅ 仅创建 |
| 查看 | ✅ 全自动 | ✅ 全自动 | ✅ 全自动 | ❌ | ✅ | ❌ |
| 修改 | ✅ 全自动 | ✅ 全自动 | ✅ 全自动 | ❌ | ✅ | ❌ |
| 删除 | ✅ 全自动 | ✅ 全自动 | ✅ 全自动 | ❌ | ✅ | ❌ |
| 参会人 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 |
| 会议邀请 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 |
| 忙闲查询 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 | 🚧 进化中 |

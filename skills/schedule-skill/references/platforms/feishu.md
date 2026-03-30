# 📘 飞书日历（需 MCP Server 或 OpenClaw）

> **重要：** 用户是电脑小白，不要主动推荐配置飞书日历全自动。
> 仅当用户**主动说**在用飞书时，才引导配置。默认走系统日历。

### 三种模式

| 模式 | 条件 | 能力 |
|------|------|------|
| **A · MCP Server 全自动** | 已配置 lark-mcp / OpenClaw 飞书插件 | 完整 CRUD |
| **B · Applink 半自动** | 安装了飞书客户端 | 仅创建（预填，需点保存） |
| **C · .ics 降级** | 任何情况 | 生成文件，手动导入 |

### 模式 A · 全自动（已配置 MCP Server 时）

**预检：** 检查 MCP 配置中是否有 `@larksuiteoapi/lark-mcp` 或 OpenClaw 飞书插件。

**MCP Server 配置参考（用户主动要求时才引导）：**

先进行 OAuth 登录：
```bash
npx -y @larksuiteoapi/lark-mcp login -a <app_id> -s <app_secret>
```

MCP 配置：
```json
{
  "mcpServers": {
    "lark-mcp": {
      "command": "npx",
      "args": ["-y", "@larksuiteoapi/lark-mcp", "mcp", "-a", "<app_id>", "-s", "<app_secret>", "-t", "preset.calendar.default", "--oauth", "--token-mode", "user_access_token"]
    }
  }
}
```

配置完成后写入记忆：
```json
{
  "feishu_mcp_configured": true,
  "feishu_mode": "lark_mcp_server",
  "qclaw_calendar_platform": "feishu_mcp"
}
```

> ⚠️ 不要在记忆中存储 app_id 和 app_secret。
> ⚠️ app_secret 会以明文存储在 MCP 配置文件中（如 `~/.codebuddy/mcp.json`）。建议提醒用户确认该文件的访问权限，避免 secret 被其他用户或程序读取。

### 模式 B · Applink 半自动

**预检：** 检测飞书客户端
- macOS: `/Applications/Lark.app` 或 `/Applications/Feishu.app`
- Windows: `%LOCALAPPDATA%\Lark\Lark.exe` 或 `%LOCALAPPDATA%\Feishu\Feishu.exe`

> ⚠️ **Applink 仅支持创建日程**（预填表单，用户需点保存）。
> 查看/修改/删除操作需要 MCP Server 全自动模式，未配置时走 .ics 降级。

**执行（通过脚本，避免 AI 心算时间戳）：**

macOS：
```bash
echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60}' | bash {SKILL_DIR}/scripts/calendar.sh open-feishu
```

Windows：
```powershell
chcp 65001 >nul && echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60}' | powershell -File {SKILL_DIR}/scripts/calendar.ps1 open-feishu
```

> 脚本内部完成：① 用 `date -j -f`（macOS）或 `.NET DateTime`（Windows）计算 Unix 时间戳 ② URL 编码标题（处理中文和特殊字符如 `&`） ③ 拼接 Applink URL ④ `open` / `Start-Process` 打开
> 输出格式: `OK|标题|开始时间戳|结束时间戳`

话术：
> "{昵称}帮你打开了飞书，信息都填好了~ 点一下「保存」就行 ✅"

### 已验证不可行的方案

- AppleScript 操控飞书 = **不行**（无 sdef）
- .ics 导入飞书 = **不行**（`open -a Lark xxx.ics` 无反应）
- `lark://` URL Scheme = 参数支持有限

### 降级链

```
① MCP Server / OpenClaw 全自动
  → ② Applink 半自动（仅创建）
    → ③ .ics 文件
      → ④ 纯文案
```

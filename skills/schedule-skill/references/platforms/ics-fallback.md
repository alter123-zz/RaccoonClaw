# 📎 .ics 兜底方案（所有平台最终降级）

> 使用 `scripts/calendar.sh generate-ics` 或 `scripts/calendar.ps1 generate-ics` 生成标准 .ics 文件。
> 文件格式详见 SKILL.md 中的 ".ics 文件格式" 段落。

**生成方式：**

macOS：
```bash
echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60}' | bash {SKILL_DIR}/scripts/calendar.sh generate-ics
```

Windows：
```powershell
chcp 65001 >nul && echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60}' | powershell -File {SKILL_DIR}/scripts/calendar.ps1 generate-ics
```

**打开方式速查：**

| 系统 | 命令 | 默认关联 |
|------|------|---------|
| macOS | `open xxx.ics` | Apple 日历 / Outlook |
| Windows | `Start-Process "xxx.ics"` | Outlook / Windows 日历 |
| Linux | `xdg-open xxx.ics` | GNOME Calendar / Thunderbird |

**话术：**
> "{昵称}帮你生成了一个日程文件，双击打开就能添加到日历啦 📎"

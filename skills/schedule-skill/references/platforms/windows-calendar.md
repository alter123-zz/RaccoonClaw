# 📅 Windows 自带日历（Windows only · Tier 2 半自动）

> **仅在 Outlook 不可用时使用。** UWP 应用不支持 COM/命令行，只能通过 .ics 文件关联。

### 预检

```powershell
powershell -File {SKILL_DIR}/scripts/calendar.ps1 detect
# 输出 windows_calendar → Windows 日历可用
```

### 执行

> 脚本 `calendar.ps1 create` 在检测到 `windows_calendar` 平台时，自动生成 .ics 文件并通过 `Start-Process` 打开。

也可通过 `outlookcal:` URI（Windows 10+，通过脚本封装避免 AI 拼接格式出错）：
```powershell
chcp 65001 >nul && echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60}' | powershell -File {SKILL_DIR}/scripts/calendar.ps1 open-outlookcal
```
> 脚本内部完成：① 计算 ISO 8601 本地时间（不带时区后缀） ② URL 编码标题 ③ 拼接 `outlookcal://` URI ④ `Start-Process` 打开
> 输出格式: `OK|标题|开始ISO时间|结束ISO时间`

### 局限性

| 能力 | Outlook COM | Windows 日历 |
|------|-------------|-------------|
| 创建 | ✅ 全自动 | ⚠️ 半自动（需用户确认保存） |
| 查看 | ✅ 全自动 | ❌ |
| 修改 | ✅ 全自动 | ❌ |
| 删除 | ✅ 全自动 | ❌ |

### 降级链

```
① .ics 文件关联打开
  → ② 纯文案
```

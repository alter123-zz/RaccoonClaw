# 📧 Outlook 日历（macOS + Windows · Tier 1 全自动）

### 预检

**macOS：**
```bash
bash {SKILL_DIR}/scripts/calendar.sh detect
# 输出 outlook_mac → Outlook 可用
```

**Windows：**
```powershell
chcp 65001 >nul && powershell -File {SKILL_DIR}/scripts/calendar.ps1 detect
# 输出 outlook_windows → Outlook COM 可用
```

### 执行

> ⚠️ **基础 CRUD 操作统一通过脚本执行**（macOS 用 `calendar.sh`，Windows 用 `calendar.ps1`），脚本自动识别 Outlook 平台。
> **参会人管理、会议邀请、忙闲查询、自定义提醒** 等高级功能正在进化中（🚧），以下代码示例仅供未来开发参考。

**macOS 基础操作（通过脚本）：**
```bash
# 创建
echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60,"location":"会议室A"}' | bash {SKILL_DIR}/scripts/calendar.sh create

# 查看
bash {SKILL_DIR}/scripts/calendar.sh list --start 2026-03-15 --end 2026-03-15

# 修改
echo '{"summary":"产品方案评审","search_date":"2026-03-15","new_start_time":"16:00"}' | bash {SKILL_DIR}/scripts/calendar.sh modify

# 删除
bash {SKILL_DIR}/scripts/calendar.sh delete --summary "产品方案评审" --date 2026-03-15
```

**Windows 基础操作（通过脚本）：**
```powershell
# 创建
chcp 65001 >nul && echo '{"summary":"产品方案评审","start_date":"2026-03-15","start_time":"15:00","duration":60}' | powershell -File {SKILL_DIR}/scripts/calendar.ps1 create

# 查看
chcp 65001 >nul && powershell -File {SKILL_DIR}/scripts/calendar.ps1 list -Start 2026-03-15 -End 2026-03-15

# 修改
chcp 65001 >nul && echo '{"summary":"产品方案评审","search_date":"2026-03-15","new_start_time":"16:00"}' | powershell -File {SKILL_DIR}/scripts/calendar.ps1 modify

# 删除
chcp 65001 >nul && powershell -File {SKILL_DIR}/scripts/calendar.ps1 delete -Summary "产品方案评审" -Date 2026-03-15
```

---

**高级功能（🚧 进化中，以下代码仅供未来开发参考）：**

注意属性名差异：

| Apple 日历 | Outlook |
|-----------|---------|
| `summary` | `subject` |
| `start date` | `start time` |
| `end date` | `end time` |

> ⚠️ **安全注意：** 以下示例中的姓名、邮箱和标题是硬编码的演示值。实际执行时，**必须用 `on run argv` 方式传参**（同 `calendar.sh` 中的做法），**不要将用户输入直接拼接到 AppleScript 代码字符串中**，否则会产生 AppleScript 注入风险（例如用户姓名中含有双引号或反斜杠时会导致语法错误或意外执行）。

创建带参会人的会议并发邀请（macOS）：
```applescript
-- 安全做法：通过 on run argv 传入用户输入
on run argv
  set evtSubject to item 1 of argv
  set attendeeName to item 2 of argv
  set attendeeEmail to item 3 of argv
  set optionalName to item 4 of argv
  set optionalEmail to item 5 of argv

  tell application "Microsoft Outlook"
    set newEvent to make new calendar event with properties {subject:evtSubject, start time:startTime, end time:endTime}
    -- 必选参会人
    make new required attendee at newEvent with properties {email address:{name:attendeeName, address:attendeeEmail}}
    -- 可选参会人
    make new optional attendee at newEvent with properties {email address:{name:optionalName, address:optionalEmail}}
    -- 发送邀请（需 Exchange/M365 账户）
    send meeting newEvent
    return "Created and sent: " & subject of newEvent
  end tell
end run
```

取消会议（发送取消通知）：
```applescript
-- 安全做法：通过 on run argv 传入标题
on run argv
  set targetSubject to item 1 of argv
  tell application "Microsoft Outlook"
    set targetEvent to first calendar event whose subject is targetSubject
    cancel meeting targetEvent
  end tell
end run
```

忙闲查询：
```applescript
tell application "Microsoft Outlook"
  query freebusy for attendees {"zhangsan@company.com", "lisi@company.com"}
end tell
```

---

**Windows PowerShell COM 高级功能（🚧 进化中，代码仅供参考）：**

> 基础 CRUD 已由 `calendar.ps1` 脚本封装，以下仅列出脚本未覆盖的高级功能（进化中）。

> ⚠️ **安全注意：** 邮箱地址等用户输入应通过变量传入，不要直接硬编码或字符串拼接。PowerShell 中变量传入本身是安全的，但不要用 `Invoke-Expression` 等方式拼接执行。

添加参会人并发邀请：
```powershell
# $attendeeEmail 应由调用方作为变量传入
$appt.MeetingStatus = 1  # olMeeting
$recipient = $appt.Recipients.Add($attendeeEmail)
$recipient.Type = 1  # 1=olRequired, 2=olOptional
$appt.Save()
$appt.Send()
```

### Outlook 跨平台能力总览

| 能力 | macOS（AppleScript） | Windows（COM） |
|------|---------------------|----------------|
| 创建日程 | ✅ 全自动 | ✅ 全自动 |
| 查看日程 | ✅ 全自动 | ✅ 全自动（支持筛选） |
| 修改日程 | ✅ 全自动 | ✅ 全自动（按 EntryID） |
| 删除日程 | ✅ 全自动 | ✅ 全自动（按 EntryID） |
| 参会人管理 | 🚧 进化中 | 🚧 进化中 |
| 发送会议邀请 | 🚧 进化中 | 🚧 进化中 |
| 取消会议 | 🚧 进化中 | 🚧 进化中 |
| 忙闲查询 | 🚧 进化中 | 🚧 进化中 |
| 提醒设置 | 🚧 进化中 | 🚧 进化中 |

### 踩坑注意

**macOS：**
- ~~属性名和 Apple 日历不同~~ → 脚本自动处理平台差异 ✅
- ~~查询不加日期过滤~~ → 脚本强制要求日期范围参数 ✅
- 参会人 email address 是 record 类型：`{name:"姓名", address:"邮箱"}`（手写时注意）
- `send meeting` 需 Exchange/M365 账户，IMAP 不行
- `attendee` 是只读聚合视图，添加必须用 `required attendee` / `optional attendee`

**Windows：**
- COM 调用可能自动启动 Outlook 并弹窗 → 静默等待就绪后再操作
- 首次 COM 调用可能弹安全提示 → 告知用户"点【允许】就行"
- ~~日期格式~~ → 脚本统一处理为 `yyyy-MM-dd HH:mm:ss` ✅
- EntryID 在同一配置文件中持久有效，可安全写入记忆

### 降级链

**macOS：**
```
① AppleScript 全自动
  → ② open -a "Microsoft Outlook" xxx.ics（半自动）
    → ③ .ics 文件下载
      → ④ 纯文案
```

**Windows：**
```
① COM 全自动
  → ② Start-Process xxx.ics（系统关联 Outlook 打开）
    → ③ .ics 文件下载
      → ④ 纯文案
```

# .ics 文件格式（降级兜底时使用）

> 仅在降级到 .ics 文件时参考此文档。脚本的 `generate-ics` 命令已内置格式处理，通常无需手动生成。

生成 .ics 文件时**必须严格遵守**以下格式：

```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//QClaw//Calendar//CN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uuid4}@qclaw
DTSTAMP:{UTC当前时间，格式 YYYYMMDDTHHmmssZ}
DTSTART;TZID={时区，如Asia/Shanghai}:{开始时间，格式 YYYYMMDDTHHmmss}
DTEND;TZID={时区，如Asia/Shanghai}:{结束时间，格式 YYYYMMDDTHHmmss}
SUMMARY:{标题}
SEQUENCE:0
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
```

**可选字段**（有值时添加，无值时不要留空行）：
- `DESCRIPTION:{描述}`
- `LOCATION:{地点}`

**格式铁律：**
1. 每行以 CRLF（`\r\n`）结尾
2. `DTSTART`/`DTEND` **必须带 TZID**，不能用裸时间戳。时区从记忆中的 `qclaw_timezone` 读取，默认 `Asia/Shanghai`
3. `DTSTAMP` **必须是 UTC 时间**（带 `Z`）
4. `UID` 必须全局唯一（用 UUID v4）
5. 文件名格式：`{标题}.ics`，中文可用

**打开方式：**
- macOS: `open "xxx.ics"`
- Windows: `Start-Process "xxx.ics"`

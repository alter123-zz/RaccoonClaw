<#
.SYNOPSIS
  QClaw 日历管理脚本 (Windows)
  零额外依赖 — 仅使用 PowerShell (系统自带)

.DESCRIPTION
  Commands:
    detect                        检测可用日历平台
    list-calendars                列出所有可写日历
    create                        创建日程 (JSON 从 stdin)
    list -Start YYYY-MM-DD -End YYYY-MM-DD  查看日程
    modify                        修改日程 (JSON 从 stdin)
    delete -Summary "名称" -Date YYYY-MM-DD   删除日程
    generate-ics                  生成 .ics 文件 (JSON 从 stdin)
    open-outlookcal               outlookcal: URI 半自动创建 (JSON 从 stdin)
    open-feishu                   飞书 Applink 半自动创建 (JSON 从 stdin)

.EXAMPLE
  echo '{"summary":"开会","start_date":"2026-03-15","start_time":"14:00"}' | powershell -File calendar.ps1 create
#>

param(
    [Parameter(Position=0)]
    [ValidateSet("detect","list-calendars","create","list","modify","delete","generate-ics","open-outlookcal","open-feishu","help")]
    [string]$Command = "help",

    # 全局参数：指定平台，跳过 detect
    [string]$Platform,

    # list 命令参数
    [string]$Start,
    [string]$End,

    # delete 命令参数
    [string]$Summary,
    [string]$Date
)

# Force UTF-8 output to prevent GBK garbled text on Chinese Windows
if ($PSVersionTable.PSVersion.Major -ge 6) {
    $OutputEncoding = [System.Text.Encoding]::UTF8
} else {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
}

$ErrorActionPreference = "Stop"

# ─── 工具函数 ───────────────────────────────────────────

# 全局平台缓存
$script:CachedPlatform = $Platform

function Get-Platform() {
    if ($script:CachedPlatform) {
        return $script:CachedPlatform
    }
    $detected = (Cmd-Detect)
    # detect 可能返回逗号分隔的多平台，取第一个作为默认
    $script:CachedPlatform = ($detected -split ",")[0]
    return $script:CachedPlatform
}

function Die([string]$msg) {
    Write-Error "ERROR: $msg"
    exit 1
}

function Validate-Date([string]$d) {
    if ($d -notmatch '^\d{4}-\d{1,2}-\d{1,2}$') {
        Die "日期格式错误: '$d'，需要 YYYY-MM-DD"
    }
    try {
        $parsed = [datetime]::ParseExact($d.PadLeft(10,'0'), "yyyy-MM-dd", $null)
        return $parsed.ToString("yyyy-MM-dd")
    } catch {
        Die "无效日期: '$d'"
    }
}

function Validate-Time([string]$t) {
    if ($t -notmatch '^\d{1,2}:\d{2}$') {
        Die "时间格式错误: '$t'，需要 HH:MM"
    }
    $parts = $t -split ':'
    $h = [int]$parts[0]
    $m = [int]$parts[1]
    if ($h -lt 0 -or $h -gt 23) { Die "小时超出范围: $h" }
    if ($m -lt 0 -or $m -gt 59) { Die "分钟超出范围: $m" }
    return @($h, $m)
}

function Read-JsonFromStdin() {
    $input_text = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($input_text)) {
        Die "请通过 stdin 传入 JSON 数据"
    }
    try {
        return $input_text | ConvertFrom-Json
    } catch {
        Die "JSON 解析失败: $_"
    }
}

function Get-OutlookApp() {
    try {
        $ol = New-Object -ComObject Outlook.Application
        return $ol
    } catch {
        return $null
    }
}

# 释放 COM 对象，防止多次调用后累积
function Release-ComObject($obj) {
    if ($obj -ne $null) {
        try {
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($obj) | Out-Null
        } catch {}
    }
}

# iCalendar TEXT 转义 (RFC 5545 §3.3.11)
function Escape-IcsText([string]$text) {
    if ([string]::IsNullOrEmpty($text)) { return $text }
    $text = $text -replace '\\', '\\'
    $text = $text -replace ';', '\;'
    $text = $text -replace ',', '\,'
    $text = $text -replace "`r`n", '\n'
    $text = $text -replace "`n", '\n'
    $text = $text -replace "`r", '\n'
    return $text
}

# ─── 公共：JSON 读取 + 起止时间计算 ─────────────────────
# 用法: $data = Read-JsonFromStdin
#       $dt = Parse-EventDateTimes $data
# 返回: @{ StartDT; EndDT; Data } 字典
function Parse-EventDateTimes($data) {
    if (-not $data.summary) { Die "缺少必填字段: summary" }
    if (-not $data.start_date) { Die "缺少必填字段: start_date (YYYY-MM-DD)" }

    $startDateStr = Validate-Date $data.start_date
    $startTimeParts = if ($data.start_time) { Validate-Time $data.start_time } else { @(9, 0) }

    $startDT = [datetime]::ParseExact($startDateStr, "yyyy-MM-dd", $null)
    $startDT = $startDT.AddHours($startTimeParts[0]).AddMinutes($startTimeParts[1])

    if ($data.end_time) {
        $endTimeParts = Validate-Time $data.end_time
        $endDT = [datetime]::ParseExact($startDateStr, "yyyy-MM-dd", $null)
        $endDT = $endDT.AddHours($endTimeParts[0]).AddMinutes($endTimeParts[1])
        if ($endDT -le $startDT) { $endDT = $endDT.AddDays(1) }
    } else {
        $duration = if ($data.duration) { [int]$data.duration } else { 60 }
        $endDT = $startDT.AddMinutes($duration)
    }

    return @{ StartDT = $startDT; EndDT = $endDT; Data = $data }
}

# ─── 公共：拼接 URI 参数 ────────────────────────────────
# 用法: Build-UriParams @{subject="编码后主题"; ...} "body" $data.description ...
function Encode-Param([string]$text) {
    return [System.Uri]::EscapeDataString($text)
}

# ─── detect: 检测可用日历平台 ──────────────────────────

function Cmd-Detect() {
    $platforms = @()

    # 1. 尝试 Outlook COM
    $ol = $null; $ns = $null; $cal = $null
    try {
        $ol = New-Object -ComObject Outlook.Application
        $ns = $ol.GetNamespace("MAPI")
        $cal = $ns.GetDefaultFolder(9)
        $name = $cal.Name
        if ($name -and $name -ne "FAIL") {
            $platforms += "outlook_windows"
        }
    } catch {
    } finally {
        Release-ComObject $cal
        Release-ComObject $ns
        Release-ComObject $ol
    }

    # 2. 尝试 Windows 自带日历
    try {
        $pkg = Get-AppxPackage -Name "microsoft.windowscommunicationsapps" -ErrorAction SilentlyContinue
        if ($pkg) {
            $platforms += "windows_calendar"
        }
    } catch {}

    # 3. 输出结果（可能包含多个平台，逗号分隔）
    if ($platforms.Count -gt 0) {
        Write-Output ($platforms -join ",")
    } else {
        Write-Output "ics_fallback"
    }
}

# ─── list-calendars: 列出日历 ─────────────────────────

function Cmd-ListCalendars() {
    $ol = $null; $ns = $null; $calFolder = $null
    try {
        $ol = Get-OutlookApp
        if (-not $ol) {
            Write-Output "UNSUPPORTED|没有检测到可用的日历应用"
            return
        }

        $ns = $ol.GetNamespace("MAPI")
        $calFolder = $ns.GetDefaultFolder(9)
        Write-Output $calFolder.Name

        # 列出其他日历文件夹
        try {
            $parent = $calFolder.Parent
            for ($i = 1; $i -le $parent.Folders.Count; $i++) {
                $folder = $parent.Folders.Item($i)
                if ($folder.DefaultItemType -eq 1 -and $folder.Name -ne $calFolder.Name) {
                    Write-Output $folder.Name
                }
            }
        } catch {}
    } finally {
        Release-ComObject $calFolder
        Release-ComObject $ns
        Release-ComObject $ol
    }
}

# ─── create: 创建日程 ─────────────────────────────────

function Cmd-Create() {
    $data = Read-JsonFromStdin
    $dt = Parse-EventDateTimes $data
    $startDT = $dt.StartDT; $endDT = $dt.EndDT

    $platform = (Get-Platform)

    switch ($platform) {
        "outlook_windows" {
            $ol = $null; $appt = $null
            try {
                $ol = Get-OutlookApp
                $appt = $ol.CreateItem(1)  # olAppointmentItem
                $appt.Subject = $data.summary
                $appt.Start = $startDT.ToString("yyyy-MM-dd HH:mm:ss")
                $appt.End = $endDT.ToString("yyyy-MM-dd HH:mm:ss")
                $appt.ReminderMinutesBeforeStart = 15

                if ($data.description) { $appt.Body = $data.description }
                if ($data.location) { $appt.Location = $data.location }

                $appt.Save()
                Write-Output "OK|$($appt.Subject)|$($appt.Start)|$($appt.End)|EntryID=$($appt.EntryID)"
            } finally {
                Release-ComObject $appt
                Release-ComObject $ol
            }
        }
        "windows_calendar" {
            # Windows 日历不支持 COM，降级到 .ics 后打开
            $icsPath = Generate-IcsFile $data $startDT $endDT $(if ($data.timezone) { $data.timezone } else { "Asia/Shanghai" })
            Start-Process $icsPath
            Write-Output "OK_ICS|$icsPath"
        }
        default {
            Write-Output "UNSUPPORTED|没有检测到可用的日历应用，请使用 generate-ics 命令"
        }
    }
}

# ─── list: 查看日程 ───────────────────────────────────

function Cmd-List([string]$startStr, [string]$endStr) {
    if (-not $startStr) { Die "缺少 -Start YYYY-MM-DD" }
    if (-not $endStr) { Die "缺少 -End YYYY-MM-DD" }

    $startStr = Validate-Date $startStr
    $endStr = Validate-Date $endStr

    $startDT = [datetime]::ParseExact($startStr, "yyyy-MM-dd", $null)
    $endDT = [datetime]::ParseExact($endStr, "yyyy-MM-dd", $null).AddHours(23).AddMinutes(59).AddSeconds(59)

    $platform = (Get-Platform)

    switch ($platform) {
        "outlook_windows" {
            $ol = $null; $ns = $null; $cal = $null; $items = $null; $filtered = $null
            try {
                $ol = Get-OutlookApp
                $ns = $ol.GetNamespace("MAPI")
                $cal = $ns.GetDefaultFolder(9)
                $items = $cal.Items
                $items.Sort("[Start]")
                $items.IncludeRecurrences = $true

                $filter = "[Start] >= '$($startDT.ToString("yyyy-MM-dd HH:mm"))' AND [Start] <= '$($endDT.ToString("yyyy-MM-dd HH:mm"))'"
                $filtered = $items.Restrict($filter)

                foreach ($item in $filtered) {
                    Write-Output "$($item.Subject)|$($item.Start)|$($item.End)|EntryID=$($item.EntryID)"
                }
            } finally {
                Release-ComObject $filtered
                Release-ComObject $items
                Release-ComObject $cal
                Release-ComObject $ns
                Release-ComObject $ol
            }
        }
        default {
            Write-Output "UNSUPPORTED|当前平台不支持查看日程"
        }
    }
}

# ─── modify: 修改日程 ─────────────────────────────────

function Cmd-Modify() {
    $data = Read-JsonFromStdin

    if (-not $data.summary) { Die "缺少必填字段: summary (要修改的日程名称)" }
    if (-not $data.search_date) { Die "缺少必填字段: search_date (YYYY-MM-DD)" }

    $searchDateStr = Validate-Date $data.search_date

    $platform = (Get-Platform)

    if ($platform -ne "outlook_windows") {
        Write-Output "UNSUPPORTED|当前平台不支持修改日程"
        return
    }

    $ol = $null; $ns = $null; $cal = $null; $items = $null; $filtered = $null
    try {
        $ol = Get-OutlookApp
        $ns = $ol.GetNamespace("MAPI")
        $cal = $ns.GetDefaultFolder(9)
        $items = $cal.Items
        $items.Sort("[Start]")
        $items.IncludeRecurrences = $true

        $searchDT = [datetime]::ParseExact($searchDateStr, "yyyy-MM-dd", $null)
        $searchEnd = $searchDT.AddDays(1)
        $safeSummary = $data.summary -replace "'", "''"
        $filter = "[Start] >= '$($searchDT.ToString("yyyy-MM-dd 00:00"))' AND [Start] < '$($searchEnd.ToString("yyyy-MM-dd 00:00"))' AND [Subject] = '$safeSummary'"
        $filtered = $items.Restrict($filter)

        $found = $null
        foreach ($item in $filtered) {
            $found = $item
            break
        }

        if (-not $found) {
            Write-Output "NOT_FOUND"
            return
        }

        # 修改标题
        if ($data.new_summary) {
            $found.Subject = $data.new_summary
        }

        # 修改开始时间
        if ($data.new_start_date -or $data.new_start_time) {
            $newStart = [datetime]$found.Start
            if ($data.new_start_date) {
                $nd = Validate-Date $data.new_start_date
                $newDateParsed = [datetime]::ParseExact($nd, "yyyy-MM-dd", $null)
                $newStart = $newDateParsed.AddHours($newStart.Hour).AddMinutes($newStart.Minute)
            }
            if ($data.new_start_time) {
                $tp = Validate-Time $data.new_start_time
                $newStart = $newStart.Date.AddHours($tp[0]).AddMinutes($tp[1])
            }
            $found.Start = $newStart.ToString("yyyy-MM-dd HH:mm:ss")
        }

        # 修改结束时间
        if ($data.new_end_time) {
            $tp = Validate-Time $data.new_end_time
            $newEnd = [datetime]$found.Start
            $newEnd = $newEnd.Date.AddHours($tp[0]).AddMinutes($tp[1])
            # 跨天检测：new_end_time 早于 Start 时日期 +1 天
            if ($newEnd -le ([datetime]$found.Start)) { $newEnd = $newEnd.AddDays(1) }
            $found.End = $newEnd.ToString("yyyy-MM-dd HH:mm:ss")
        } elseif ($data.new_duration) {
            $found.End = ([datetime]$found.Start).AddMinutes([int]$data.new_duration).ToString("yyyy-MM-dd HH:mm:ss")
        }

        $found.Save()
        Write-Output "OK|$($found.Subject)|$($found.Start)|$($found.End)"
    } finally {
        Release-ComObject $filtered
        Release-ComObject $items
        Release-ComObject $cal
        Release-ComObject $ns
        Release-ComObject $ol
    }
}

# ─── delete: 删除日程 ─────────────────────────────────

function Cmd-Delete([string]$summaryStr, [string]$dateStr) {
    if (-not $summaryStr) { Die "缺少 -Summary" }
    if (-not $dateStr) { Die "缺少 -Date YYYY-MM-DD" }

    $dateStr = Validate-Date $dateStr

    $platform = (Get-Platform)

    if ($platform -ne "outlook_windows") {
        Write-Output "UNSUPPORTED|当前平台不支持删除日程"
        return
    }

    $ol = $null; $ns = $null; $cal = $null; $items = $null; $filtered = $null
    try {
        $ol = Get-OutlookApp
        $ns = $ol.GetNamespace("MAPI")
        $cal = $ns.GetDefaultFolder(9)
        $items = $cal.Items
        $items.Sort("[Start]")
        $items.IncludeRecurrences = $true

        $searchDT = [datetime]::ParseExact($dateStr, "yyyy-MM-dd", $null)
        $searchEnd = $searchDT.AddDays(1)
        $safeSummary = $summaryStr -replace "'", "''"
        $filter = "[Start] >= '$($searchDT.ToString("yyyy-MM-dd 00:00"))' AND [Start] < '$($searchEnd.ToString("yyyy-MM-dd 00:00"))' AND [Subject] = '$safeSummary'"
        $filtered = $items.Restrict($filter)

        $found = $null
        foreach ($item in $filtered) {
            $found = $item
            break
        }

        if (-not $found) {
            Write-Output "NOT_FOUND"
            return
        }

        $info = "$($found.Subject)|$($found.Start)|$($found.End)"
        $found.Delete()
        Write-Output "OK|$info"
    } finally {
        Release-ComObject $filtered
        Release-ComObject $items
        Release-ComObject $cal
        Release-ComObject $ns
        Release-ComObject $ol
    }
}

# ─── generate-ics: 生成 .ics 文件 ─────────────────────

function Generate-IcsFile($data, [datetime]$startDT, [datetime]$endDT, [string]$timezone = "Asia/Shanghai") {
    $outputDir = if ($data.output_dir) { $data.output_dir } else { "." }

    # 清理文件名：替换危险字符为下划线，防止路径遍历和文件创建失败
    $safeSummary = $data.summary -replace '[/\\:*?"<>|]', '_' -replace '\.\.', '_'
    $filepath = Join-Path $outputDir "$safeSummary.ics"

    $uid = [guid]::NewGuid().ToString()
    $dtstamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $dtstart = $startDT.ToString("yyyyMMddTHHmmss")
    $dtend = $endDT.ToString("yyyyMMddTHHmmss")

    $lines = @(
        "BEGIN:VCALENDAR"
        "VERSION:2.0"
        "PRODID:-//QClaw//Calendar//CN"
        "CALSCALE:GREGORIAN"
        "METHOD:PUBLISH"
        "BEGIN:VEVENT"
        "UID:${uid}@qclaw"
        "DTSTAMP:$dtstamp"
        "DTSTART;TZID=${timezone}:$dtstart"
        "DTEND;TZID=${timezone}:$dtend"
        "SUMMARY:$(Escape-IcsText $data.summary)"
    )

    if ($data.description) { $lines += "DESCRIPTION:$(Escape-IcsText $data.description)" }
    if ($data.location) { $lines += "LOCATION:$(Escape-IcsText $data.location)" }

    $lines += @(
        "SEQUENCE:0"
        "STATUS:CONFIRMED"
        "END:VEVENT"
        "END:VCALENDAR"
    )

    # CRLF 行尾
    $content = ($lines -join "`r`n") + "`r`n"
    [System.IO.File]::WriteAllText($filepath, $content, [System.Text.Encoding]::UTF8)

    return $filepath
}

function Cmd-GenerateIcs() {
    $data = Read-JsonFromStdin
    $dt = Parse-EventDateTimes $data
    $startDT = $dt.StartDT; $endDT = $dt.EndDT

    $filepath = Generate-IcsFile $data $startDT $endDT $(if ($data.timezone) { $data.timezone } else { "Asia/Shanghai" })
    Write-Output "OK|$filepath"
}

# ─── open-outlookcal: outlookcal: URI 半自动创建 ───────

function Cmd-OpenOutlookCal() {
    $data = Read-JsonFromStdin
    $dt = Parse-EventDateTimes $data
    $startDT = $dt.StartDT; $endDT = $dt.EndDT

    $startIso = $startDT.ToString("yyyy-MM-ddTHH:mm:ss")
    $endIso = $endDT.ToString("yyyy-MM-ddTHH:mm:ss")

    $url = "outlookcal://content?subject=$(Encode-Param $data.summary)&startdt=$startIso&enddt=$endIso"
    if ($data.description) { $url += "&body=$(Encode-Param $data.description)" }
    if ($data.location) { $url += "&location=$(Encode-Param $data.location)" }

    try {
        Start-Process $url
        Write-Output "OK|$($data.summary)|$startIso|$endIso"
    } catch {
        Write-Output "ERROR|无法打开 outlookcal: URI: $_"
    }
}

# ─── open-feishu: 飞书 Applink 半自动创建 ──────────────

function Cmd-OpenFeishu() {
    $data = Read-JsonFromStdin
    $dt = Parse-EventDateTimes $data
    $startDT = $dt.StartDT; $endDT = $dt.EndDT

    $epoch = [datetime]::new(1970, 1, 1, 0, 0, 0, [System.DateTimeKind]::Utc)
    $startTs = [int64]($startDT.ToUniversalTime() - $epoch).TotalSeconds
    $endTs = [int64]($endDT.ToUniversalTime() - $epoch).TotalSeconds

    $url = "https://applink.feishu.cn/client/calendar/event/create?summary=$(Encode-Param $data.summary)&start_time=$startTs&end_time=$endTs"
    if ($data.description) { $url += "&description=$(Encode-Param $data.description)" }
    if ($data.location) { $url += "&location=$(Encode-Param $data.location)" }

    try {
        Start-Process $url
        Write-Output "OK|$($data.summary)|$startTs|$endTs"
    } catch {
        Write-Output "ERROR|无法打开飞书 Applink: $_"
    }
}

# ─── 主入口 ───────────────────────────────────────────

switch ($Command) {
    "detect"          { Cmd-Detect }
    "list-calendars"  { Cmd-ListCalendars }
    "create"          { Cmd-Create }
    "list"            { Cmd-List $Start $End }
    "modify"          { Cmd-Modify }
    "delete"          { Cmd-Delete $Summary $Date }
    "generate-ics"    { Cmd-GenerateIcs }
    "open-outlookcal" { Cmd-OpenOutlookCal }
    "open-feishu"     { Cmd-OpenFeishu }
    "help" {
        Write-Output @"
QClaw 日历管理脚本 (Windows)

Commands:
  detect                        检测可用日历平台
  list-calendars                列出所有可写日历
  create                        创建日程 (JSON 从 stdin)
  list -Start D -End D          查看日程 (D=YYYY-MM-DD)
  modify                        修改日程 (JSON 从 stdin)
  delete -Summary S -Date D     删除日程
  generate-ics                  生成 .ics 文件 (JSON 从 stdin)
  open-outlookcal               outlookcal: URI 半自动创建 (JSON 从 stdin)
  open-feishu                   飞书 Applink 半自动创建 (JSON 从 stdin)

JSON 字段 (create / open-outlookcal / open-feishu):
  summary      (必填) 日程标题
  start_date   (必填) 开始日期 YYYY-MM-DD
  start_time   开始时间 HH:MM (默认 09:00)
  end_time     结束时间 HH:MM (与 duration 二选一)
  duration     时长分钟数 (默认 60)
  description  描述
  location     地点

JSON 字段 (modify):
  summary      (必填) 要修改的日程名称
  search_date  (必填) 日程所在日期 YYYY-MM-DD
  new_summary  新标题
  new_start_date  新日期 YYYY-MM-DD
  new_start_time  新开始时间 HH:MM
  new_end_time    新结束时间 HH:MM
  new_duration    新时长分钟数

JSON 字段 (generate-ics):
  同 create，额外支持 output_dir (输出目录，默认当前目录)
  timezone     时区 IANA 标识 (默认 Asia/Shanghai)
"@
    }
}

# ─── COM 清理 ─────────────────────────────────────────
# 确保 Outlook COM 对象被释放，防止进程残留
try {
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
} catch {}

#!/bin/bash
# QClaw 日历管理脚本 (macOS)
# 零额外依赖 — 仅使用 bash + osascript (系统自带)
#
# Usage: calendar.sh <command> [options]
#
# Commands:
#   detect                        检测可用日历平台
#   list-calendars                列出所有可写日历
#   create    < json              创建日程 (JSON 从 stdin)
#   list      --start YYYY-MM-DD --end YYYY-MM-DD   查看日程
#   modify    < json              修改日程 (JSON 从 stdin)
#   delete    --summary "名称" --date YYYY-MM-DD     删除日程
#   generate-ics < json           生成 .ics 文件 (JSON 从 stdin)
#   open-feishu < json            飞书 Applink 半自动创建 (JSON 从 stdin)
#   open-outlookcal < json        outlookcal: URI 半自动创建 (JSON 从 stdin)

set -euo pipefail

# ─── 工具函数 ───────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }

# 全局平台缓存（通过 --platform 参数传入或自动 detect）
PLATFORM=""
_PLATFORM_CACHE_FILE="/tmp/.qclaw_platform_$$"

# 获取当前平台：优先用缓存，没有则 detect（多平台时取第一个）
# 修复：原实现在 $() 子 shell 中赋值 PLATFORM 无法回传到父 shell
# 现改用临时文件缓存，同一进程内不重复 detect
get_platform() {
  if [ -n "$PLATFORM" ]; then
    echo "$PLATFORM"
  elif [ -f "$_PLATFORM_CACHE_FILE" ]; then
    cat "$_PLATFORM_CACHE_FILE"
  else
    local detected
    detected=$(cmd_detect)
    local first="${detected%%,*}"
    echo "$first" > "$_PLATFORM_CACHE_FILE"
    echo "$first"
  fi
}

_cleanup_platform_cache() { rm -f "$_PLATFORM_CACHE_FILE" 2>/dev/null; }
trap _cleanup_platform_cache EXIT

# 验证日期格式 YYYY-MM-DD，返回规范化的零填充日期
validate_date() {
  local d="$1"
  [[ "$d" =~ ^([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})$ ]] || die "日期格式错误: '$d'，需要 YYYY-MM-DD"
  local y="${BASH_REMATCH[1]}" m="${BASH_REMATCH[2]}" dd="${BASH_REMATCH[3]}"
  (( m >= 1 && m <= 12 )) || die "月份超出范围: $m"
  (( dd >= 1 && dd <= 31 )) || die "日期超出范围: $dd"
  printf '%04d-%02d-%02d' "$y" "$m" "$dd"
}

# 验证时间格式 HH:MM，返回 hour 和 minute
validate_time() {
  local t="$1"
  [[ "$t" =~ ^([0-9]{1,2}):([0-9]{2})$ ]] || die "时间格式错误: '$t'，需要 HH:MM"
  local h="${BASH_REMATCH[1]}" m="${BASH_REMATCH[2]}"
  (( h >= 0 && h <= 23 )) || die "小时超出范围: $h"
  (( m >= 0 && m <= 59 )) || die "分钟超出范围: $m"
  echo "$h $m"
}

# 从 JSON 字符串中提取字段值 (纯 bash + osascript，不依赖 jq/python)
# 安全：JSON 通过 stdin 传入，不拼接到 JS 代码中
json_get() {
  local json="$1" field="$2" default="${3:-}"
  local val
  val=$(printf '%s' "$json" | osascript -l JavaScript -e '
    ObjC.import("Foundation");
    var data = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
    var str = $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding).js;
    var d = JSON.parse(str);
    var v = d["'"$field"'"];
    (v === undefined || v === null) ? "" : String(v);
  ' 2>/dev/null) || val=""
  if [ -z "$val" ]; then echo "$default"; else echo "$val"; fi
}

# 批量从 JSON 提取多个字段 (优先用 python3，fallback 到 osascript)
json_get_batch() {
  local json="$1"; shift
  local fields=("$@")
  if command -v python3 &>/dev/null; then
    printf '%s' "$json" | python3 -c '
import sys, json
data = json.loads(sys.stdin.read())
for f in sys.argv[1:]:
    v = data.get(f)
    print("" if v is None else str(v))
' "${fields[@]}"
  else
    printf '%s' "$json" | osascript -l JavaScript - "${fields[@]}" <<'JSCODE'
    ObjC.import("Foundation");
    var args = $.NSProcessInfo.processInfo.arguments;
    var data = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile;
    var str = $.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding).js;
    var d = JSON.parse(str);
    var results = [];
    for (var i = 4; i < args.count; i++) {
      var key = ObjC.unwrap(args.objectAtIndex(i));
      var v = d[key];
      results.push((v === undefined || v === null) ? "" : String(v));
    }
    results.join("\n");
JSCODE
  fi
}

# ─── 公共：从 stdin 读 JSON 并批量提取字段到 _F 数组 ─────
# 用法: parse_json_fields "field1" "field2" ...
# 结果存入全局数组 _F[]（下标从 0 开始）
_F=()
parse_json_fields() {
  local json
  json=$(cat)
  [ -n "$json" ] || die "请通过 stdin 传入 JSON 数据"

  local _batch_result
  _batch_result=$(json_get_batch "$json" "$@") || true

  _F=()
  while IFS= read -r _line; do
    _F+=("$_line")
  done <<< "$_batch_result"
}

# ─── 公共：URL 编码 ─────────────────────────────────────
# 优先 python3，fallback 到 osascript JavaScript
url_encode() {
  local text="$1"
  if command -v python3 &>/dev/null; then
    python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$text"
  else
    osascript -l JavaScript -e "encodeURIComponent('$(printf '%s' "$text" | sed "s/'/\\\\'/g")')"
  fi
}

# ─── 公共：计算 Unix 时间戳（秒级精确）────────────────
# 用法: date_to_epoch "YYYY-MM-DD" "HH:MM"
date_to_epoch() {
  date -j -f "%Y-%m-%d %H:%M:%S" "$1 $2:00" "+%s" 2>/dev/null
}

# ─── 公共：根据 start_date/start_time + end_time|duration 计算 end epoch ─
# 用法: calc_end_epoch "$start_epoch" "$start_date" "$end_time" "$duration"
# 输出: end 的 Unix 时间戳
calc_end_epoch() {
  local start_epoch="$1" start_date="$2" end_time="$3" duration="${4:-60}"
  if [ -n "$end_time" ]; then
    validate_time "$end_time" >/dev/null
    local end_epoch
    end_epoch=$(date_to_epoch "$start_date" "$end_time") || die "无法计算结束时间"
    # 跨天修复
    if [ "$end_epoch" -le "$start_epoch" ]; then
      end_epoch=$(( end_epoch + 86400 ))
    fi
    echo "$end_epoch"
  else
    echo $(( start_epoch + duration * 60 ))
  fi
}

# ─── detect: 检测可用日历平台 ──────────────────────────
# 合并为单次 osascript 调用（原先两次分别检测，各 ~100-200ms）
# 使用 try-catch 避免未安装 app 时弹出系统对话框

cmd_detect() {
  local result
  result=$(osascript <<'APPLESCRIPT'
set platforms to ""
try
  tell application "Calendar" to get name of first calendar
  set platforms to "apple_calendar"
end try
try
  tell application "Microsoft Outlook" to get name
  if platforms is "" then
    set platforms to "outlook_mac"
  else
    set platforms to platforms & ",outlook_mac"
  end if
end try
if platforms is "" then
  return "ics_fallback"
else
  return platforms
end if
APPLESCRIPT
  ) 2>/dev/null || result=""

  if [ -n "$result" ]; then
    echo "$result"
  else
    echo "ics_fallback"
  fi
  return 0
}

# ─── list-calendars: 列出可写日历 ─────────────────────

cmd_list_calendars() {
  local platform
  platform=$(get_platform)

  case "$platform" in
    apple_calendar)
      osascript -e '
        tell application "Calendar"
          set output to ""
          repeat with c in calendars
            if writable of c then
              set output to output & name of c & linefeed
            end if
          end repeat
          return output
        end tell
      '
      ;;
    outlook_mac)
      osascript -e '
        tell application "Microsoft Outlook"
          set output to ""
          repeat with c in calendars
            set output to output & name of c & linefeed
          end repeat
          return output
        end tell
      '
      ;;
    *)
      echo "UNSUPPORTED|没有检测到可用的日历应用"
      return 0
      ;;
  esac
}

# ─── create: 创建日程 ─────────────────────────────────

cmd_create() {
  parse_json_fields summary calendar start_date start_time end_time duration description location

  local summary="${_F[0]:-}" calendar="${_F[1]:-}" start_date="${_F[2]:-}"
  local start_time="${_F[3]:-09:00}" end_time="${_F[4]:-}" duration="${_F[5]:-60}"
  local description="${_F[6]:-}" location="${_F[7]:-}"

  [ -n "$summary" ] || die "缺少必填字段: summary"
  [ -n "$start_date" ] || die "缺少必填字段: start_date (YYYY-MM-DD)"
  start_date=$(validate_date "$start_date")
  local st_parts
  st_parts=$(validate_time "$start_time")
  local start_hour start_minute
  start_hour=$(echo "$st_parts" | cut -d' ' -f1)
  start_minute=$(echo "$st_parts" | cut -d' ' -f2)

  local platform
  platform=$(get_platform)

  case "$platform" in
    apple_calendar)
      # 使用 on run argv 传参，防止注入
      # AppleScript 日期铁律：先 set day to 1，再设 year/month/day
      # 日历选择已合并到 AppleScript 内部：若 calName 为空则自动选第一个可写日历
      osascript - "$summary" "$start_date" "$start_hour" "$start_minute" \
        "$duration" "$end_time" "$description" "$location" "$calendar" <<'APPLESCRIPT'
on run argv
  set evtSummary to item 1 of argv
  set isoDate to item 2 of argv
  set evtHour to (item 3 of argv) as integer
  set evtMinute to (item 4 of argv) as integer
  set durationMin to (item 5 of argv) as integer
  set endTimeStr to item 6 of argv
  set evtDescription to item 7 of argv
  set evtLocation to item 8 of argv
  set calName to item 9 of argv

  -- 若未指定日历，自动选择第一个可写日历（合并到此处减少一次 osascript 调用）
  if calName is "" then
    tell application "Calendar"
      set calName to name of first calendar whose writable is true
    end tell
  end if

  -- 安全设置日期（跨月铁律：先置1号，再设年/月/日）
  set startDate to current date
  set day of startDate to 1
  set year of startDate to (text 1 thru 4 of isoDate) as integer
  set month of startDate to (text 6 thru 7 of isoDate) as integer
  set day of startDate to (text 9 thru 10 of isoDate) as integer
  set hours of startDate to evtHour
  set minutes of startDate to evtMinute
  set seconds of startDate to 0

  -- 计算结束时间
  if endTimeStr is not "" then
    set endDate to current date
    set day of endDate to 1
    set year of endDate to (text 1 thru 4 of isoDate) as integer
    set month of endDate to (text 6 thru 7 of isoDate) as integer
    set day of endDate to (text 9 thru 10 of isoDate) as integer
    set endHour to (text 1 thru 2 of endTimeStr) as integer
    set endMin to (text 4 thru 5 of endTimeStr) as integer
    set hours of endDate to endHour
    set minutes of endDate to endMin
    set seconds of endDate to 0
  else
    set endDate to startDate + durationMin * minutes
  end if

  tell application "Calendar"
    if not (writable of calendar calName) then
      error "日历 '" & calName & "' 是只读的"
    end if
    tell calendar calName
      set eventProps to {summary:evtSummary, start date:startDate, end date:endDate}
      set newEvent to make new event at end of events with properties eventProps
      if evtDescription is not "" then
        set description of newEvent to evtDescription
      end if
      if evtLocation is not "" then
        set location of newEvent to evtLocation
      end if
    end tell
  end tell

  return "OK|" & evtSummary & "|" & startDate & "|" & endDate
end run
APPLESCRIPT
      ;;

    outlook_mac)
      osascript - "$summary" "$start_date" "$start_hour" "$start_minute" \
        "$duration" "$end_time" "$description" "$location" <<'APPLESCRIPT'
on run argv
  set evtSummary to item 1 of argv
  set isoDate to item 2 of argv
  set evtHour to (item 3 of argv) as integer
  set evtMinute to (item 4 of argv) as integer
  set durationMin to (item 5 of argv) as integer
  set endTimeStr to item 6 of argv
  set evtDescription to item 7 of argv
  set evtLocation to item 8 of argv

  set startDate to current date
  set day of startDate to 1
  set year of startDate to (text 1 thru 4 of isoDate) as integer
  set month of startDate to (text 6 thru 7 of isoDate) as integer
  set day of startDate to (text 9 thru 10 of isoDate) as integer
  set hours of startDate to evtHour
  set minutes of startDate to evtMinute
  set seconds of startDate to 0

  if endTimeStr is not "" then
    set endDate to current date
    set day of endDate to 1
    set year of endDate to (text 1 thru 4 of isoDate) as integer
    set month of endDate to (text 6 thru 7 of isoDate) as integer
    set day of endDate to (text 9 thru 10 of isoDate) as integer
    set endHour to (text 1 thru 2 of endTimeStr) as integer
    set endMin to (text 4 thru 5 of endTimeStr) as integer
    set hours of endDate to endHour
    set minutes of endDate to endMin
    set seconds of endDate to 0
  else
    set endDate to startDate + durationMin * minutes
  end if

  tell application "Microsoft Outlook"
    set eventProps to {subject:evtSummary, start time:startDate, end time:endDate}
    set newEvent to make new calendar event with properties eventProps
    if evtDescription is not "" then
      set content of newEvent to evtDescription
    end if
    if evtLocation is not "" then
      set location of newEvent to evtLocation
    end if
  end tell

  return "OK|" & evtSummary & "|" & startDate & "|" & endDate
end run
APPLESCRIPT
      ;;

    *)
      echo "UNSUPPORTED|没有检测到可用的日历应用，请使用 generate-ics 命令"
      return 0
      ;;
  esac
}

# ─── list: 查看日程 ───────────────────────────────────

cmd_list() {
  local start_date="" end_date=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --start) start_date="$2"; shift 2 ;;
      --end)   end_date="$2";   shift 2 ;;
      *) die "未知参数: $1" ;;
    esac
  done

  [ -n "$start_date" ] || die "缺少 --start YYYY-MM-DD"
  [ -n "$end_date" ]   || die "缺少 --end YYYY-MM-DD"

  start_date=$(validate_date "$start_date")
  end_date=$(validate_date "$end_date")

  local platform
  platform=$(get_platform)

  case "$platform" in
    apple_calendar)
      osascript - "$start_date" "$end_date" <<'APPLESCRIPT'
on run argv
  set startISO to item 1 of argv
  set endISO to item 2 of argv

  set startDate to current date
  set day of startDate to 1
  set year of startDate to (text 1 thru 4 of startISO) as integer
  set month of startDate to (text 6 thru 7 of startISO) as integer
  set day of startDate to (text 9 thru 10 of startISO) as integer
  set time of startDate to 0

  set endDate to current date
  set day of endDate to 1
  set year of endDate to (text 1 thru 4 of endISO) as integer
  set month of endDate to (text 6 thru 7 of endISO) as integer
  set day of endDate to (text 9 thru 10 of endISO) as integer
  set time of endDate to 86399 -- 23:59:59

  set output to ""
  tell application "Calendar"
    repeat with cal in calendars
      set evts to (every event of cal whose start date ≥ startDate and start date ≤ endDate)
      repeat with e in evts
        set output to output & (summary of e) & "|" & (start date of e) & "|" & (end date of e) & "|" & (name of cal) & linefeed
      end repeat
    end repeat
  end tell
  return output
end run
APPLESCRIPT
      ;;

    outlook_mac)
      osascript - "$start_date" "$end_date" <<'APPLESCRIPT'
on run argv
  set startISO to item 1 of argv
  set endISO to item 2 of argv

  set startDate to current date
  set day of startDate to 1
  set year of startDate to (text 1 thru 4 of startISO) as integer
  set month of startDate to (text 6 thru 7 of startISO) as integer
  set day of startDate to (text 9 thru 10 of startISO) as integer
  set time of startDate to 0

  set endDate to current date
  set day of endDate to 1
  set year of endDate to (text 1 thru 4 of endISO) as integer
  set month of endDate to (text 6 thru 7 of endISO) as integer
  set day of endDate to (text 9 thru 10 of endISO) as integer
  set time of endDate to 86399

  set output to ""
  tell application "Microsoft Outlook"
    set evts to (every calendar event whose start time ≥ startDate and start time ≤ endDate)
    repeat with e in evts
      set output to output & (subject of e) & "|" & (start time of e) & "|" & (end time of e) & linefeed
    end repeat
  end tell
  return output
end run
APPLESCRIPT
      ;;

    *)
      echo "UNSUPPORTED|当前平台不支持查看日程"
      return 0
      ;;
  esac
}

# ─── modify: 修改日程 ─────────────────────────────────

cmd_modify() {
  parse_json_fields summary search_date new_summary new_start_date new_start_time new_end_time new_duration

  local summary="${_F[0]:-}" search_date="${_F[1]:-}" new_summary="${_F[2]:-}"
  local new_start_date="${_F[3]:-}" new_start_time="${_F[4]:-}"
  local new_end_time="${_F[5]:-}" new_duration="${_F[6]:-}"

  [ -n "$summary" ] || die "缺少必填字段: summary (要修改的日程名称)"
  [ -n "$search_date" ] || die "缺少必填字段: search_date (YYYY-MM-DD)"
  search_date=$(validate_date "$search_date")

  # 至少要改一项
  if [ -z "$new_summary" ] && [ -z "$new_start_date" ] && [ -z "$new_start_time" ] && [ -z "$new_end_time" ]; then
    die "至少提供一个要修改的字段: new_summary / new_start_date / new_start_time / new_end_time"
  fi

  # 验证新日期/时间格式
  if [ -n "$new_start_date" ]; then
    new_start_date=$(validate_date "$new_start_date")
  fi
  if [ -n "$new_start_time" ]; then
    validate_time "$new_start_time" >/dev/null
  fi
  if [ -n "$new_end_time" ]; then
    validate_time "$new_end_time" >/dev/null
  fi

  local platform
  platform=$(get_platform)

  case "$platform" in
    apple_calendar)
      osascript - "$summary" "$search_date" "$new_summary" "$new_start_date" \
        "$new_start_time" "$new_end_time" "$new_duration" <<'APPLESCRIPT'
on run argv
  set targetSummary to item 1 of argv
  set searchISO to item 2 of argv
  set newSummary to item 3 of argv
  set newDateISO to item 4 of argv
  set newStartTimeStr to item 5 of argv
  set newEndTimeStr to item 6 of argv
  set newDurationStr to item 7 of argv

  -- 搜索日期范围 (当天 00:00 ~ 23:59)
  set searchStart to current date
  set day of searchStart to 1
  set year of searchStart to (text 1 thru 4 of searchISO) as integer
  set month of searchStart to (text 6 thru 7 of searchISO) as integer
  set day of searchStart to (text 9 thru 10 of searchISO) as integer
  set time of searchStart to 0

  set searchEnd to searchStart + 1 * days

  set foundEvent to missing value
  tell application "Calendar"
    repeat with cal in calendars
      if writable of cal then
        set evts to (every event of cal whose summary is targetSummary and start date ≥ searchStart and start date < searchEnd)
        if (count of evts) > 0 then
          set foundEvent to item 1 of evts
          exit repeat
        end if
      end if
    end repeat

    if foundEvent is missing value then
      return "NOT_FOUND"
    end if

    -- 修改标题
    if newSummary is not "" then
      set summary of foundEvent to newSummary
    end if

    -- 修改日期和时间
    if newDateISO is not "" or newStartTimeStr is not "" then
      set newStart to start date of foundEvent
      if newDateISO is not "" then
        set day of newStart to 1
        set year of newStart to (text 1 thru 4 of newDateISO) as integer
        set month of newStart to (text 6 thru 7 of newDateISO) as integer
        set day of newStart to (text 9 thru 10 of newDateISO) as integer
      end if
      if newStartTimeStr is not "" then
        set hours of newStart to (text 1 thru 2 of newStartTimeStr) as integer
        set minutes of newStart to (text 4 thru 5 of newStartTimeStr) as integer
        set seconds of newStart to 0
      end if
      set start date of foundEvent to newStart
    end if

    if newEndTimeStr is not "" then
      set newEnd to end date of foundEvent
      if newDateISO is not "" then
        set day of newEnd to 1
        set year of newEnd to (text 1 thru 4 of newDateISO) as integer
        set month of newEnd to (text 6 thru 7 of newDateISO) as integer
        set day of newEnd to (text 9 thru 10 of newDateISO) as integer
      end if
      set hours of newEnd to (text 1 thru 2 of newEndTimeStr) as integer
      set minutes of newEnd to (text 4 thru 5 of newEndTimeStr) as integer
      set seconds of newEnd to 0
      set end date of foundEvent to newEnd
    else if newDurationStr is not "" then
      set end date of foundEvent to (start date of foundEvent) + (newDurationStr as integer) * minutes
    end if

    return "OK|" & summary of foundEvent & "|" & start date of foundEvent & "|" & end date of foundEvent
  end tell
end run
APPLESCRIPT
      ;;

    outlook_mac)
      osascript - "$summary" "$search_date" "$new_summary" "$new_start_date" \
        "$new_start_time" "$new_end_time" "$new_duration" <<'APPLESCRIPT'
on run argv
  set targetSubject to item 1 of argv
  set searchISO to item 2 of argv
  set newSubject to item 3 of argv
  set newDateISO to item 4 of argv
  set newStartTimeStr to item 5 of argv
  set newEndTimeStr to item 6 of argv
  set newDurationStr to item 7 of argv

  set searchStart to current date
  set day of searchStart to 1
  set year of searchStart to (text 1 thru 4 of searchISO) as integer
  set month of searchStart to (text 6 thru 7 of searchISO) as integer
  set day of searchStart to (text 9 thru 10 of searchISO) as integer
  set time of searchStart to 0
  set searchEnd to searchStart + 1 * days

  set foundEvent to missing value
  tell application "Microsoft Outlook"
    set evts to (every calendar event whose subject is targetSubject and start time ≥ searchStart and start time < searchEnd)
    if (count of evts) > 0 then
      set foundEvent to item 1 of evts
    end if

    if foundEvent is missing value then
      return "NOT_FOUND"
    end if

    if newSubject is not "" then
      set subject of foundEvent to newSubject
    end if

    if newDateISO is not "" or newStartTimeStr is not "" then
      set newStart to start time of foundEvent
      if newDateISO is not "" then
        set day of newStart to 1
        set year of newStart to (text 1 thru 4 of newDateISO) as integer
        set month of newStart to (text 6 thru 7 of newDateISO) as integer
        set day of newStart to (text 9 thru 10 of newDateISO) as integer
      end if
      if newStartTimeStr is not "" then
        set hours of newStart to (text 1 thru 2 of newStartTimeStr) as integer
        set minutes of newStart to (text 4 thru 5 of newStartTimeStr) as integer
      end if
      set start time of foundEvent to newStart
    end if

    if newEndTimeStr is not "" then
      set newEnd to end time of foundEvent
      if newDateISO is not "" then
        set day of newEnd to 1
        set year of newEnd to (text 1 thru 4 of newDateISO) as integer
        set month of newEnd to (text 6 thru 7 of newDateISO) as integer
        set day of newEnd to (text 9 thru 10 of newDateISO) as integer
      end if
      set hours of newEnd to (text 1 thru 2 of newEndTimeStr) as integer
      set minutes of newEnd to (text 4 thru 5 of newEndTimeStr) as integer
      set end time of foundEvent to newEnd
    else if newDurationStr is not "" then
      set end time of foundEvent to (start time of foundEvent) + (newDurationStr as integer) * minutes
    end if

    return "OK|" & subject of foundEvent & "|" & start time of foundEvent & "|" & end time of foundEvent
  end tell
end run
APPLESCRIPT
      ;;

    *)
      echo "UNSUPPORTED|当前平台不支持修改日程"
      return 0
      ;;
  esac
}

# ─── delete: 删除日程 ─────────────────────────────────

cmd_delete() {
  local summary="" search_date=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --summary) summary="$2"; shift 2 ;;
      --date)    search_date="$2"; shift 2 ;;
      *) die "未知参数: $1" ;;
    esac
  done

  [ -n "$summary" ]     || die "缺少 --summary"
  [ -n "$search_date" ] || die "缺少 --date YYYY-MM-DD"
  search_date=$(validate_date "$search_date")

  local platform
  platform=$(get_platform)

  case "$platform" in
    apple_calendar)
      osascript - "$summary" "$search_date" <<'APPLESCRIPT'
on run argv
  set targetSummary to item 1 of argv
  set searchISO to item 2 of argv

  set searchStart to current date
  set day of searchStart to 1
  set year of searchStart to (text 1 thru 4 of searchISO) as integer
  set month of searchStart to (text 6 thru 7 of searchISO) as integer
  set day of searchStart to (text 9 thru 10 of searchISO) as integer
  set time of searchStart to 0
  set searchEnd to searchStart + 1 * days

  tell application "Calendar"
    repeat with cal in calendars
      if writable of cal then
        set evts to (every event of cal whose summary is targetSummary and start date ≥ searchStart and start date < searchEnd)
        if (count of evts) > 0 then
          -- 删除前记录信息用于结果输出
          set targetEvent to item 1 of evts
          set info to (summary of targetEvent) & "|" & (start date of targetEvent) & "|" & (end date of targetEvent)
          delete targetEvent
          return "OK|" & info
        end if
      end if
    end repeat
    return "NOT_FOUND"
  end tell
end run
APPLESCRIPT
      ;;

    outlook_mac)
      osascript - "$summary" "$search_date" <<'APPLESCRIPT'
on run argv
  set targetSubject to item 1 of argv
  set searchISO to item 2 of argv

  set searchStart to current date
  set day of searchStart to 1
  set year of searchStart to (text 1 thru 4 of searchISO) as integer
  set month of searchStart to (text 6 thru 7 of searchISO) as integer
  set day of searchStart to (text 9 thru 10 of searchISO) as integer
  set time of searchStart to 0
  set searchEnd to searchStart + 1 * days

  tell application "Microsoft Outlook"
    set evts to (every calendar event whose subject is targetSubject and start time ≥ searchStart and start time < searchEnd)
    if (count of evts) > 0 then
      set targetEvent to item 1 of evts
      set info to (subject of targetEvent) & "|" & (start time of targetEvent) & "|" & (end time of targetEvent)
      delete targetEvent
      return "OK|" & info
    end if
    return "NOT_FOUND"
  end tell
end run
APPLESCRIPT
      ;;

    *)
      echo "UNSUPPORTED|当前平台不支持删除日程"
      return 0
      ;;
  esac
}

# ─── generate-ics: 生成 .ics 文件 ─────────────────────

cmd_generate_ics() {
  parse_json_fields summary start_date start_time end_time duration description location output_dir timezone

  local summary="${_F[0]:-}" start_date="${_F[1]:-}" start_time="${_F[2]:-09:00}"
  local end_time="${_F[3]:-}" duration="${_F[4]:-60}" description="${_F[5]:-}"
  local location="${_F[6]:-}" output_dir="${_F[7]:-.}" timezone="${_F[8]:-Asia/Shanghai}"

  [ -n "$summary" ] || die "缺少必填字段: summary"
  [ -n "$start_date" ] || die "缺少必填字段: start_date (YYYY-MM-DD)"
  start_date=$(validate_date "$start_date")
  validate_time "$start_time" >/dev/null

  # 格式化时间为 iCal 格式 YYYYMMDDTHHMMSS
  local dt_start dt_end
  dt_start="${start_date//-/}T${start_time//:}00"

  if [ -n "$end_time" ]; then
    validate_time "$end_time" >/dev/null
    # 跨天检测：end_time < start_time 时日期 +1 天
    local end_date="$start_date"
    if [[ "$end_time" < "$start_time" ]]; then
      end_date=$(date -j -v+1d -f "%Y-%m-%d" "$start_date" "+%Y-%m-%d" 2>/dev/null)
    fi
    dt_end="${end_date//-/}T${end_time//:}00"
  else
    # 用 duration 计算结束时间（正确处理跨天：22:00 + 180min → 次日 01:00）
    local end_epoch end_formatted
    end_epoch=$(date -j -f "%Y-%m-%d %H:%M" "${start_date} ${start_time}" "+%s" 2>/dev/null)
    end_epoch=$(( end_epoch + duration * 60 ))
    end_formatted=$(date -j -f "%s" "$end_epoch" "+%Y%m%dT%H%M00" 2>/dev/null)
    dt_end="$end_formatted"
  fi

  # UTC 时间戳
  local dtstamp
  dtstamp=$(date -u +%Y%m%dT%H%M%SZ)

  # UUID
  local uid
  uid=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "$(date +%s)-$$-qclaw")

  # 清理文件名：替换危险字符为下划线，防止路径遍历和文件创建失败
  local safe_summary
  safe_summary=$(printf '%s' "$summary" | tr '/\\:*?"<>|' '_' | sed 's/\.\./_/g')
  local filepath="${output_dir}/${safe_summary}.ics"

  # 生成 .ics 内容 (CRLF 行尾)
  {
    printf 'BEGIN:VCALENDAR\r\n'
    printf 'VERSION:2.0\r\n'
    printf 'PRODID:-//QClaw//Calendar//CN\r\n'
    printf 'CALSCALE:GREGORIAN\r\n'
    printf 'METHOD:PUBLISH\r\n'
    printf 'BEGIN:VEVENT\r\n'
    printf 'UID:%s@qclaw\r\n' "$uid"
    printf 'DTSTAMP:%s\r\n' "$dtstamp"
    printf 'DTSTART;TZID=%s:%s\r\n' "$timezone" "$dt_start"
    printf 'DTEND;TZID=%s:%s\r\n' "$timezone" "$dt_end"
    printf 'SUMMARY:%s\r\n' "$summary"
    [ -n "$description" ] && printf 'DESCRIPTION:%s\r\n' "$description"
    [ -n "$location" ] && printf 'LOCATION:%s\r\n' "$location"
    printf 'SEQUENCE:0\r\n'
    printf 'STATUS:CONFIRMED\r\n'
    printf 'END:VEVENT\r\n'
    printf 'END:VCALENDAR\r\n'
  } > "$filepath"

  echo "OK|${filepath}"
}

# ─── open-feishu: 飞书 Applink 半自动创建 ──────────────

cmd_open_feishu() {
  parse_json_fields summary start_date start_time end_time duration description location

  local summary="${_F[0]:-}" start_date="${_F[1]:-}" start_time="${_F[2]:-09:00}"
  local end_time="${_F[3]:-}" duration="${_F[4]:-60}" description="${_F[5]:-}" location="${_F[6]:-}"

  [ -n "$summary" ] || die "缺少必填字段: summary"
  [ -n "$start_date" ] || die "缺少必填字段: start_date (YYYY-MM-DD)"
  start_date=$(validate_date "$start_date")
  validate_time "$start_time" >/dev/null

  local start_ts end_ts
  start_ts=$(date_to_epoch "$start_date" "$start_time") || die "无法计算开始时间的 Unix 时间戳"
  end_ts=$(calc_end_epoch "$start_ts" "$start_date" "$end_time" "$duration")

  # URL 编码 + 拼接 Applink URL
  local url="https://applink.feishu.cn/client/calendar/event/create?summary=$(url_encode "$summary")&start_time=${start_ts}&end_time=${end_ts}"
  [ -n "$description" ] && url="${url}&description=$(url_encode "$description")"
  [ -n "$location" ] && url="${url}&location=$(url_encode "$location")"

  open "$url" 2>/dev/null || die "无法打开飞书 Applink URL"
  echo "OK|${summary}|${start_ts}|${end_ts}"
}

# ─── open-outlookcal: outlookcal: URI 半自动创建 ────────

cmd_open_outlookcal() {
  parse_json_fields summary start_date start_time end_time duration description location

  local summary="${_F[0]:-}" start_date="${_F[1]:-}" start_time="${_F[2]:-09:00}"
  local end_time="${_F[3]:-}" duration="${_F[4]:-60}" description="${_F[5]:-}" location="${_F[6]:-}"

  [ -n "$summary" ] || die "缺少必填字段: summary"
  [ -n "$start_date" ] || die "缺少必填字段: start_date (YYYY-MM-DD)"
  start_date=$(validate_date "$start_date")
  validate_time "$start_time" >/dev/null

  # 计算 ISO 8601 本地时间（不带时区后缀）
  local start_iso end_iso
  start_iso="${start_date}T${start_time}:00"

  if [ -n "$end_time" ]; then
    validate_time "$end_time" >/dev/null
    local st_epoch et_epoch
    st_epoch=$(date_to_epoch "$start_date" "$start_time")
    et_epoch=$(date_to_epoch "$start_date" "$end_time")
    if [ "$et_epoch" -le "$st_epoch" ]; then
      local next_date
      next_date=$(date -j -v+1d -f "%Y-%m-%d" "$start_date" "+%Y-%m-%d" 2>/dev/null)
      end_iso="${next_date}T${end_time}:00"
    else
      end_iso="${start_date}T${end_time}:00"
    fi
  else
    local end_epoch end_formatted_date end_formatted_time
    end_epoch=$(date_to_epoch "$start_date" "$start_time")
    end_epoch=$(( end_epoch + duration * 60 ))
    end_formatted_date=$(date -j -f "%s" "$end_epoch" "+%Y-%m-%d" 2>/dev/null)
    end_formatted_time=$(date -j -f "%s" "$end_epoch" "+%H:%M" 2>/dev/null)
    end_iso="${end_formatted_date}T${end_formatted_time}:00"
  fi

  # 拼接 outlookcal:// URI
  local url="outlookcal://content?subject=$(url_encode "$summary")&startdt=${start_iso}&enddt=${end_iso}"
  [ -n "$description" ] && url="${url}&body=$(url_encode "$description")"
  [ -n "$location" ] && url="${url}&location=$(url_encode "$location")"

  open "$url" 2>/dev/null || die "无法打开 outlookcal: URI"
  echo "OK|${summary}|${start_iso}|${end_iso}"
}

# ─── 主入口 ───────────────────────────────────────────

# 解析全局 --platform 参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform)
      PLATFORM="$2"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done

cmd="${1:-help}"
shift || true

case "$cmd" in
  detect)           cmd_detect ;;
  list-calendars)   cmd_list_calendars ;;
  create)           cmd_create ;;
  list)             cmd_list "$@" ;;
  modify)           cmd_modify ;;
  delete)           cmd_delete "$@" ;;
  generate-ics)     cmd_generate_ics ;;
  open-feishu)      cmd_open_feishu ;;
  open-outlookcal)  cmd_open_outlookcal ;;
  help|*)
    echo "QClaw 日历管理脚本 (macOS)"
    echo ""
    echo "Commands:"
    echo "  detect                        检测可用日历平台"
    echo "  list-calendars                列出所有可写日历"
    echo "  create    < json              创建日程"
    echo "  list      --start D --end D   查看日程 (D=YYYY-MM-DD)"
    echo "  modify    < json              修改日程"
    echo "  delete    --summary S --date D  删除日程"
    echo "  generate-ics < json           生成 .ics 文件"
    echo "  open-feishu < json            飞书 Applink 半自动创建"
    echo "  open-outlookcal < json        outlookcal: URI 半自动创建"
    echo ""
    echo "JSON 字段 (create / open-feishu / open-outlookcal):"
    echo "  summary      (必填) 日程标题"
    echo "  start_date   (必填) 开始日期 YYYY-MM-DD"
    echo "  start_time   开始时间 HH:MM (默认 09:00)"
    echo "  end_time     结束时间 HH:MM (与 duration 二选一)"
    echo "  duration     时长分钟数 (默认 60)"
    echo "  calendar     日历名称 (仅 create: 自动选择第一个可写日历)"
    echo "  description  描述"
    echo "  location     地点"
    echo ""
    echo "JSON 字段 (modify):"
    echo "  summary      (必填) 要修改的日程名称"
    echo "  search_date  (必填) 日程所在日期 YYYY-MM-DD"
    echo "  new_summary  新标题"
    echo "  new_start_date  新日期 YYYY-MM-DD"
    echo "  new_start_time  新开始时间 HH:MM"
    echo "  new_end_time    新结束时间 HH:MM"
    echo "  new_duration    新时长分钟数"
    echo ""
    echo "JSON 字段 (generate-ics):"
    echo "  同 create，额外支持 output_dir (输出目录，默认当前目录)"
    echo "  timezone     时区 IANA 标识 (默认 Asia/Shanghai)"
    ;;
esac

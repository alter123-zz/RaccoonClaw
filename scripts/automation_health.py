#!/usr/bin/env python3
"""Cron automation health snapshot for the workbench."""

from __future__ import annotations

import datetime as _dt
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from file_lock import atomic_json_read, atomic_json_write
from incident_playbook import build_incident_summary, classify_incident
from intake_guard import analyze_message
from runtime_paths import canonical_data_dir


OCLAW_HOME = Path.home() / ".openclaw"
CRON_JOBS_PATH = OCLAW_HOME / "cron" / "jobs.json"
CRON_RUNS_DIR = OCLAW_HOME / "cron" / "runs"
WALLSTREET_LIVE_URL = "https://wallstreetcn.com/live/global"
WALLSTREET_API_URL = "https://api-one-wscn.awtmt.com/apiv1/content/lives"
CLS_TELEGRAPH_URL = "https://www.cls.cn/telegraph"
WALLSTREET_TICKER_CACHE_PATH = canonical_data_dir() / "wallstreet_news_ticker.json"
WALLSTREET_TICKER_REFRESH_MS = 15 * 60 * 1000
WALLSTREET_TICKER_LIMIT = 24
WALLSTREET_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": WALLSTREET_LIVE_URL,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
CLS_HEADERS = {
    "User-Agent": WALLSTREET_HEADERS["User-Agent"],
    "Accept-Language": WALLSTREET_HEADERS["Accept-Language"],
    "Referer": CLS_TELEGRAPH_URL,
}
_WALLSTREET_KEYWORDS = (
    "ai", "人工智能", "大模型", "llm", "gpt", "chatgpt", "openai", "anthropic", "claude",
    "gemini", "deepseek", "豆包", "文心", "算力", "gpu", "英伟达", "nvidia", "amd", "芯片",
    "半导体", "处理器", "科技", "技术", "互联网", "云计算", "机器人", "自动驾驶", "智能驾驶",
    "量子", "卫星", "浏览器", "软件", "开源", "安全",
)
_POLITICAL_EXCLUSION_KEYWORDS = (
    "特朗普", "伊朗", "以色列", "乌克兰", "俄罗斯", "巴基斯坦", "阿富汗", "黎巴嫩",
    "停火", "袭击", "空袭", "导弹", "军方", "军队", "军舰", "防空", "无人机袭击",
    "大使馆", "外交", "总统", "总理", "海峡", "国务院", "白宫", "新华社", "央视",
    "军事行动", "交火", "核武器", "领袖", "使馆",
)
_WALLSTREET_CATEGORY_LABELS = {
    "AI": "🔥 AI/科技热点",
    "TECH": "⚡ 科技动态",
    "ENERGY": "⚡ 科技赛道",
    "DEFAULT": "科技快讯",
}

_ERROR_STATUSES = {"error", "failed", "timeout"}
_DELIVERY_ERROR_STATUSES = {"error", "failed", "undelivered"}
_WALLSTREET_JOB_TOKENS = ("华尔街见闻", "wallstreet")
_SUMMARY_ARTIFACT_ROOTS = (Path("/tmp"), Path("/private/tmp"), OCLAW_HOME)


def _fmt_hm(hour: str, minute: str) -> str:
    return f"{int(hour):02d}:{int(minute):02d}"


def _humanize_schedule(expr: str) -> str:
    parts = str(expr or "").strip().split()
    if len(parts) != 5:
        return str(expr or "")

    minute, hour, dom, month, dow = parts

    if minute.startswith("*/") and hour == "*" and dom == "*" and month == "*" and dow == "*":
        try:
            step = int(minute[2:])
            if step > 0:
                return f"每{step}分钟"
        except Exception:
            return str(expr or "")

    if dom != "*" or month != "*" or dow != "*":
        return str(expr or "")

    if minute.isdigit() and "," in hour and all(item.isdigit() for item in hour.split(",")):
        times = "、".join(_fmt_hm(item, minute) for item in hour.split(","))
        return f"每日 {times}"

    if minute.isdigit() and "-" in hour:
        start, end = hour.split("-", 1)
        if start.isdigit() and end.isdigit():
            if minute == "0":
                return f"每日 {_fmt_hm(start, minute)}-{_fmt_hm(end, minute)} 每小时整点"
            return f"每日 {_fmt_hm(start, minute)}-{_fmt_hm(end, minute)}"

    if minute == "0" and hour == "*":
        return "每小时整点"

    if minute.isdigit() and hour.isdigit():
        return f"每日 {_fmt_hm(hour, minute)}"

    return str(expr or "")


def _route_label(route_mode: str, direct_agent_hint: str = "") -> str:
    if route_mode == "direct_reply":
        return "直接回复"
    if route_mode == "direct_handle":
        return "总裁办直办"
    if route_mode == "direct_execute":
        dept = {
            "engineering": "工程研发部",
            "business_analysis": "经营分析部",
            "brand_content": "品牌内容部",
            "secops": "安全运维部",
            "compliance_test": "合规测试部",
            "people_ops": "人力组织部",
            "chief_of_staff": "总裁办",
        }.get(direct_agent_hint, "对应部门")
        return f"一步直派 · {dept}"
    if route_mode == "create_task":
        return "完整协同链"
    return ""


def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _now_ms() -> int:
    return int(_now_utc().timestamp() * 1000)


def _iso_from_ms(ms: Any) -> str | None:
    if not isinstance(ms, (int, float)) or ms <= 0:
        return None
    return _dt.datetime.fromtimestamp(ms / 1000, tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_run_events(job_id: str, limit: int = 8) -> list[dict[str, Any]]:
    path = CRON_RUNS_DIR / f"{job_id}.jsonl"
    if not path.exists():
        return []
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []
    if not lines:
        return []

    events: list[dict[str, Any]] = []
    for line in reversed(lines[-limit:]):
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _read_last_run_event(job_id: str) -> dict[str, Any]:
    events = _read_run_events(job_id, limit=1)
    return events[0] if events else {}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _fallback_wallstreet_title(content: str, limit: int = 42) -> str:
    normalized = _clean_text(content)
    if not normalized:
        return "未命名快讯"
    sentence = re.split(r"[。！？!?；;]", normalized)[0].strip()
    head = sentence or normalized
    return head[:limit] + ("..." if len(head) > limit else "")


def _wallstreet_category(text: str) -> str:
    lowered = str(text or "").lower()
    if any(token in lowered for token in ("ai", "人工智能", "大模型", "llm", "gpt", "chatgpt", "openai", "claude", "deepseek", "豆包")):
        return "AI"
    if any(token in lowered for token in ("新能源", "电池", "储能", "光伏", "风电", "核电", "氢能")):
        return "ENERGY"
    if any(token in lowered for token in ("科技", "技术", "芯片", "半导体", "机器人", "卫星", "浏览器", "软件", "开源", "安全", "云计算")):
        return "TECH"
    return "DEFAULT"


def _is_excluded_ticker_item(text: str) -> bool:
    return any(token in str(text or "") for token in _POLITICAL_EXCLUSION_KEYWORDS)


def _wallstreet_item_time(value: Any) -> str:
    if isinstance(value, (int, float)) and value > 0:
        dt = _dt.datetime.fromtimestamp(value, tz=_dt.timezone.utc).astimezone(_dt.timezone(_dt.timedelta(hours=8)))
        return dt.strftime("%H:%M")
    text = _clean_text(str(value or ""))
    match = re.search(r"(\d{2}):(\d{2})(?::\d{2})?$", text)
    if match:
        return f"{match.group(1)}:{match.group(2)}"
    return ""


def _fetch_wallstreet_live_items(limit: int = WALLSTREET_TICKER_LIMIT) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "channel": "global-channel",
            "client": "pc",
            "limit": int(limit),
            "first_page": "true",
            "accept": "live,vip-live",
        }
    )
    request = urllib.request.Request(f"{WALLSTREET_API_URL}?{params}", headers=WALLSTREET_HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("data", {}).get("items", []) if isinstance(payload, dict) else []


def _fetch_cls_live_items(limit: int = WALLSTREET_TICKER_LIMIT) -> list[dict[str, Any]]:
    request = urllib.request.Request(CLS_TELEGRAPH_URL, headers=CLS_HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw_html = response.read().decode("utf-8", errors="ignore")

    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", raw_html, flags=re.S | re.I)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.S | re.I)
    cleaned = re.sub(r"<[^>]+>", "\n", cleaned)
    cleaned = html.unescape(cleaned).replace("\xa0", " ")
    cleaned = re.sub(r"\r", "", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)

    results: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?P<time>\d{2}:\d{2}:\d{2})\s+〖(?P<title>[^〗]+)〗(?P<content>.*?)(?=\n\d{2}:\d{2}:\d{2}\n+〖|\Z)",
        re.S,
    )
    for match in pattern.finditer(cleaned):
        title = _clean_text(match.group("title"))
        content = _clean_text(match.group("content"))
        content = re.split(r"\s+(?:阅\s+\d|评论\s*\(|分享\(|环球市场情报|电报持续更新中)", content)[0].strip()
        if not title and not content:
            continue
        results.append(
            {
                "id": f"cls:{match.group('time')}:{len(results) + 1}",
                "time": match.group("time"),
                "title": title,
                "content_text": content,
                "source": "财联社电报",
                "sourceUrl": CLS_TELEGRAPH_URL,
            }
        )
        if len(results) >= limit:
            break
    return results


def _build_live_wallstreet_items(limit: int = 8) -> list[dict[str, Any]]:
    raw_items = _fetch_wallstreet_live_items(limit=WALLSTREET_TICKER_LIMIT)
    cls_items = _fetch_cls_live_items(limit=WALLSTREET_TICKER_LIMIT)
    items: list[dict[str, Any]] = []

    for raw in raw_items:
        title = _clean_text(raw.get("title", ""))
        content = _clean_text(raw.get("content_text", "") or raw.get("content_more", ""))
        if not title:
            title = _fallback_wallstreet_title(content)

        haystack = f"{title} {content}".lower()
        if _is_excluded_ticker_item(f"{title} {content}"):
            continue
        if not any(keyword in haystack for keyword in _WALLSTREET_KEYWORDS):
            continue

        category_key = _wallstreet_category(haystack)
        item_id = str(raw.get("id") or "")
        items.append(
            {
                "id": item_id or f"wscn:{len(items) + 1}",
                "time": _wallstreet_item_time(raw.get("display_time") or raw.get("time")),
                "title": title,
                "summary": content[:160],
                "category": _WALLSTREET_CATEGORY_LABELS.get(category_key, "科技快讯"),
                "source": "华尔街见闻快讯",
                "sourceUrl": f"https://wallstreetcn.com/livenews/{item_id}" if item_id else WALLSTREET_LIVE_URL,
            }
        )

    for raw in cls_items:
        title = _clean_text(raw.get("title", ""))
        content = _clean_text(raw.get("content_text", ""))
        haystack = f"{title} {content}".lower()
        if _is_excluded_ticker_item(f"{title} {content}"):
            continue
        if not any(keyword in haystack for keyword in _WALLSTREET_KEYWORDS):
            continue

        category_key = _wallstreet_category(haystack)
        items.append(
            {
                "id": str(raw.get("id") or f"cls:{len(items) + 1}"),
                "time": _wallstreet_item_time(raw.get("time")),
                "title": title,
                "summary": content[:160],
                "category": _WALLSTREET_CATEGORY_LABELS.get(category_key, "科技快讯"),
                "source": "财联社电报",
                "sourceUrl": CLS_TELEGRAPH_URL,
            }
        )

    items.sort(key=lambda item: item.get("time") or "", reverse=True)
    return items[:limit]


def _read_cached_wallstreet_ticker() -> dict[str, Any] | None:
    cached = atomic_json_read(WALLSTREET_TICKER_CACHE_PATH, {})
    if not isinstance(cached, dict):
        return None
    fetched_at_ms = cached.get("fetchedAtMs")
    items = cached.get("items")
    if not isinstance(fetched_at_ms, (int, float)) or not isinstance(items, list) or not items:
        return None
    if cached.get("source") != "华尔街见闻 / 财联社快讯":
        return None
    for item in items:
        title = _clean_text(str(item.get("title") or ""))
        summary = _clean_text(str(item.get("summary") or ""))
        haystack = f"{title} {summary}".lower()
        if _is_excluded_ticker_item(f"{title} {summary}"):
            return None
        if not any(keyword in haystack for keyword in _WALLSTREET_KEYWORDS):
            return None
    return cached


def _fetch_or_build_wallstreet_ticker(raw_jobs: list[dict[str, Any]], now_ms: int) -> dict[str, Any]:
    cached = _read_cached_wallstreet_ticker()
    if cached and now_ms - int(cached.get("fetchedAtMs") or 0) <= WALLSTREET_TICKER_REFRESH_MS:
        return cached

    try:
        items = _build_live_wallstreet_items(limit=8)
        if items:
            payload = {
                "source": "华尔街见闻 / 财联社快讯",
                "sourceUrl": WALLSTREET_LIVE_URL,
                "jobId": "",
                "jobName": "科技快讯板块",
                "updatedAt": _iso_from_ms(now_ms),
                "headline": items[0]["title"],
                "count": len(items),
                "items": items,
                "refreshMinutes": 15,
                "refreshLabel": "每15分钟刷新",
                "fetchedAtMs": now_ms,
            }
            atomic_json_write(WALLSTREET_TICKER_CACHE_PATH, payload)
            return payload
    except Exception:
        pass

    fallback = _build_news_ticker(raw_jobs)
    if fallback.get("items"):
        fallback["refreshMinutes"] = 15
        fallback["refreshLabel"] = "每15分钟刷新"
        fallback["fetchedAtMs"] = now_ms
        return fallback

    if cached:
        cached["refreshMinutes"] = 15
        cached["refreshLabel"] = "每15分钟刷新"
        return cached

    return {
        "source": "华尔街见闻快讯",
        "sourceUrl": WALLSTREET_LIVE_URL,
        "jobId": "",
        "jobName": "科技快讯板块",
        "updatedAt": None,
        "headline": "",
        "count": 0,
        "items": [],
        "refreshMinutes": 15,
        "refreshLabel": "每15分钟刷新",
    }


def _load_summary_artifact(summary: str) -> str:
    match = re.search(r"(/(?:tmp|private/tmp)/[^\s`'\"]+\.txt)", str(summary or ""))
    if not match:
        return ""

    candidate = Path(match.group(1)).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except Exception:
        return ""

    if not any(str(resolved).startswith(str(root)) for root in _SUMMARY_ARTIFACT_ROOTS):
        return ""

    try:
        return resolved.read_text(encoding="utf-8")
    except Exception:
        return ""


def _extract_wallstreet_items_from_bullets(summary: str, job_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    category = "科技快讯"

    for raw_line in str(summary or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith(":") and line[:1] in {"🔥", "⚡", "📈", "📊"}:
            category = line.rstrip(":").strip()
            continue
        if not line.startswith("•"):
            continue

        body = line.lstrip("•").strip()
        time_match = re.match(r"^\[(\d{2}:\d{2})\]\s*(.+)$", body)
        if time_match:
            time_text = time_match.group(1)
            body = time_match.group(2).strip()
        else:
            time_text = ""

        title, sep, detail = body.partition(" - ")
        title = _clean_text(title or body)
        detail = _clean_text(detail if sep else "")
        if not title:
            continue

        items.append(
            {
                "id": f"{job_id}:{len(items) + 1}",
                "time": time_text,
                "title": title,
                "summary": detail,
                "category": category,
                "source": "华尔街见闻快讯",
                "sourceUrl": WALLSTREET_LIVE_URL,
            }
        )

    return items


def _extract_wallstreet_items_from_longform(summary: str, job_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    sections = [section.strip() for section in re.split(r"\n\s*---\s*\n", str(summary or "")) if section.strip()]
    for section in sections:
        title_match = re.search(r"^[🔥⚡📈📊]\s*(?:\d+\.\s*)?(.+)$", section, flags=re.MULTILINE)
        if not title_match:
            continue

        title = _clean_text(title_match.group(1))
        if not title or title.startswith("今日市场关键词") or "华尔街见闻科技快讯" in title:
            continue

        comment_match = re.search(r"^💬\s*(.+)$", section, flags=re.MULTILINE)
        summary_text = _clean_text(comment_match.group(1)) if comment_match else ""
        link_match = re.search(r"^🔗\s*(https?://\S+)", section, flags=re.MULTILINE)
        source_url = _clean_text(link_match.group(1)) if link_match else WALLSTREET_LIVE_URL

        items.append(
            {
                "id": f"{job_id}:{len(items) + 1}",
                "time": "",
                "title": title,
                "summary": summary_text,
                "category": "🔥 AI/科技热点",
                "source": "华尔街见闻快讯",
                "sourceUrl": source_url,
            }
        )

    return items


def _extract_wallstreet_items(summary: str, job_id: str) -> list[dict[str, Any]]:
    primary_text = str(summary or "")
    for candidate in (primary_text, _load_summary_artifact(primary_text)):
        if not candidate:
            continue
        items = _extract_wallstreet_items_from_bullets(candidate, job_id)
        if items:
            return items
        items = _extract_wallstreet_items_from_longform(candidate, job_id)
        if items:
            return items
    return []


def _extract_wallstreet_items_from_compact_summary(summary: str, job_id: str) -> list[dict[str, Any]]:
    compact = _clean_text(summary)
    if not compact:
        return []

    selected_match = re.search(r'选中[“"](.+?)[”"]', compact)
    title = _clean_text(selected_match.group(1)) if selected_match else ""
    if not title:
        title_match = re.search(r"评论生成.+?(?:股票代码|\$).+?", compact)
        if not title_match:
            return []
        title = "华尔街见闻科技快讯精选"

    return [
        {
            "id": f"{job_id}:compact:1",
            "time": "",
            "title": title,
            "summary": compact,
            "category": "🔥 AI/科技热点",
            "source": "华尔街见闻快讯",
            "sourceUrl": WALLSTREET_LIVE_URL,
        }
    ]


def _build_news_ticker(raw_jobs: list[dict[str, Any]]) -> dict[str, Any]:
    candidates: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    for job in raw_jobs:
        if not isinstance(job, dict):
            continue
        name = str(job.get("name") or "")
        lowered = name.lower()
        if not any(token in name or token in lowered for token in _WALLSTREET_JOB_TOKENS):
            continue
        state = job.get("state") if isinstance(job.get("state"), dict) else {}
        last_run_ms = int(state.get("lastRunAtMs") or 0)
        last_event = _read_last_run_event(str(job.get("id") or ""))
        if not last_run_ms:
            last_run_ms = int(last_event.get("runAtMs") or last_event.get("ts") or 0)
        candidates.append((last_run_ms, job, last_event))

    candidates.sort(key=lambda item: item[0], reverse=True)

    for last_run_ms, job, last_event in candidates:
        run_events = _read_run_events(str(job.get("id") or ""), limit=8)
        fallback_item: list[dict[str, Any]] = []
        fallback_run_ms = last_run_ms

        for event in run_events or [last_event]:
            event_run_ms = int(event.get("runAtMs") or event.get("ts") or last_run_ms or 0)
            summary = str(event.get("summary") or "")
            items = _extract_wallstreet_items(summary, str(job.get("id") or ""))
            if items:
                return {
                    "source": "华尔街见闻快讯",
                    "sourceUrl": WALLSTREET_LIVE_URL,
                    "jobId": str(job.get("id") or ""),
                    "jobName": str(job.get("name") or "华尔街见闻定时抓取"),
                    "updatedAt": _iso_from_ms(event_run_ms),
                    "headline": items[0]["title"],
                    "count": len(items),
                    "items": items[:8],
                }
            if not fallback_item:
                fallback_item = _extract_wallstreet_items_from_compact_summary(summary, str(job.get("id") or ""))
                fallback_run_ms = event_run_ms or fallback_run_ms

        if fallback_item:
            return {
                "source": "华尔街见闻快讯",
                "sourceUrl": WALLSTREET_LIVE_URL,
                "jobId": str(job.get("id") or ""),
                "jobName": str(job.get("name") or "华尔街见闻定时抓取"),
                "updatedAt": _iso_from_ms(fallback_run_ms),
                "headline": fallback_item[0]["title"],
                "count": len(fallback_item),
                "items": fallback_item,
            }

    return {
        "source": "华尔街见闻快讯",
        "sourceUrl": WALLSTREET_LIVE_URL,
        "jobId": "",
        "jobName": "华尔街见闻定时抓取",
        "updatedAt": None,
        "headline": "",
        "count": 0,
        "items": [],
    }


def _estimate_interval_ms(expr: str, state: dict[str, Any]) -> int | None:
    last_run = state.get("lastRunAtMs")
    next_run = state.get("nextRunAtMs")
    if isinstance(last_run, (int, float)) and isinstance(next_run, (int, float)):
        diff = int(next_run - last_run)
        if 60_000 <= diff <= 14 * 24 * 60 * 60 * 1000:
            return diff

    parts = str(expr or "").strip().split()
    if len(parts) != 5:
        return None
    minute, hour, dom, month, dow = parts

    if minute.startswith("*/"):
        try:
            step = int(minute[2:])
            if step > 0:
                return step * 60 * 1000
        except Exception:
            pass

    if "," in minute and hour == "*":
        values = [item for item in minute.split(",") if item]
        if values:
            return max(5 * 60 * 1000, int(60 * 60 * 1000 / len(values)))

    if dom == "*" and month == "*" and dow == "*":
        if hour == "*":
            return 60 * 60 * 1000
        if "-" in hour:
            return 60 * 60 * 1000
        if "," in hour:
            values = [item for item in hour.split(",") if item]
            if values:
                return max(60 * 60 * 1000, int(24 * 60 * 60 * 1000 / len(values)))
        if hour.isdigit():
            return 24 * 60 * 60 * 1000

    if dow != "*":
        return 7 * 24 * 60 * 60 * 1000
    if dom != "*":
        return 24 * 60 * 60 * 1000
    return None


def _grace_ms(interval_ms: int | None) -> int:
    if not interval_ms:
        return 10 * 60 * 1000
    return max(5 * 60 * 1000, min(30 * 60 * 1000, interval_ms // 4))


def _status_rank(status: str) -> int:
    return {"critical": 0, "warning": 1, "healthy": 2, "pending": 3, "paused": 4}.get(status, 9)


def _build_job_snapshot(job: dict[str, Any], now_ms: int) -> dict[str, Any]:
    state = job.get("state") if isinstance(job.get("state"), dict) else {}
    schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
    delivery = job.get("delivery") if isinstance(job.get("delivery"), dict) else {}
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    last_event = _read_last_run_event(str(job.get("id") or ""))
    route_info = analyze_message(str(payload.get("message") or "")) if payload.get("message") else {}
    route_mode = str(route_info.get("routeMode") or "")
    direct_agent_hint = str(route_info.get("directAgentHint") or "")

    last_run_status = str(
        state.get("lastRunStatus")
        or state.get("lastStatus")
        or last_event.get("status")
        or ""
    ).strip()
    last_delivery_status = str(
        state.get("lastDeliveryStatus")
        or last_event.get("deliveryStatus")
        or ""
    ).strip()
    consecutive_errors = int(state.get("consecutiveErrors") or 0)
    next_run_ms = state.get("nextRunAtMs")
    last_run_ms = state.get("lastRunAtMs") or last_event.get("runAtMs") or last_event.get("ts")
    interval_ms = _estimate_interval_ms(str(schedule.get("expr") or ""), state)
    grace_ms = _grace_ms(interval_ms)
    overdue_ms = (
        max(0, now_ms - int(next_run_ms))
        if isinstance(next_run_ms, (int, float))
        else 0
    )

    status = "healthy"
    tone = "ok"
    message = "运行正常"

    if not job.get("enabled", True):
        status = "paused"
        tone = "muted"
        message = "任务已暂停"
    elif consecutive_errors > 0 or last_run_status.lower() in _ERROR_STATUSES or last_delivery_status.lower() in _DELIVERY_ERROR_STATUSES:
        status = "critical"
        tone = "err"
        error_text = str(last_event.get("error") or "").strip()
        if error_text:
            message = error_text[:120]
        elif last_delivery_status.lower() in _DELIVERY_ERROR_STATUSES:
            message = f"最近一次投递失败: {last_delivery_status}"
        else:
            message = f"最近一次执行异常: {last_run_status or 'unknown'}"
    elif isinstance(next_run_ms, (int, float)) and overdue_ms > grace_ms:
        status = "warning"
        tone = "warn"
        if last_run_ms:
            message = "已超过计划执行时间，未观察到新的执行记录"
        else:
            message = "首轮执行已超时，请检查任务是否真正启动"
    elif not last_run_ms:
        status = "pending"
        tone = "warn"
        message = "等待首次执行"

    snapshot = {
        "id": str(job.get("id") or ""),
        "name": str(job.get("name") or "未命名自动化"),
        "agentId": str(job.get("agentId") or ""),
        "enabled": bool(job.get("enabled", True)),
        "status": status,
        "tone": tone,
        "message": message,
        "scheduleExpr": str(schedule.get("expr") or ""),
        "scheduleLabel": _humanize_schedule(str(schedule.get("expr") or "")),
        "timezone": str(schedule.get("tz") or "Asia/Shanghai"),
        "routeMode": route_mode,
        "routeLabel": _route_label(route_mode, direct_agent_hint),
        "routeReason": str(route_info.get("reason") or ""),
        "directAgentHint": direct_agent_hint,
        "channel": str(delivery.get("channel") or ""),
        "target": str(delivery.get("to") or ""),
        "lastRunAtMs": int(last_run_ms) if isinstance(last_run_ms, (int, float)) else None,
        "lastRunAt": _iso_from_ms(last_run_ms),
        "nextRunAtMs": int(next_run_ms) if isinstance(next_run_ms, (int, float)) else None,
        "nextRunAt": _iso_from_ms(next_run_ms),
        "lastRunStatus": last_run_status or "unknown",
        "lastDeliveryStatus": last_delivery_status or "unknown",
        "lastDurationMs": int(state.get("lastDurationMs") or last_event.get("durationMs") or 0),
        "consecutiveErrors": consecutive_errors,
        "overdueMs": overdue_ms,
        "graceMs": grace_ms,
        "intervalMs": interval_ms,
        "lastError": str(last_event.get("error") or "").strip(),
    }
    snapshot["incident"] = classify_incident(snapshot, now_ms)
    return snapshot


def build_automation_snapshot() -> dict[str, Any]:
    jobs_payload = _read_json(CRON_JOBS_PATH, {})
    raw_jobs = jobs_payload.get("jobs", []) if isinstance(jobs_payload, dict) else []
    if not isinstance(raw_jobs, list):
        raw_jobs = []

    now_ms = _now_ms()
    jobs = [_build_job_snapshot(job, now_ms) for job in raw_jobs if isinstance(job, dict)]
    jobs.sort(key=lambda item: (_status_rank(str(item.get("status") or "")), item.get("nextRunAtMs") or 0, item.get("name") or ""))

    alerts = [job for job in jobs if job.get("status") in {"warning", "critical"}]
    incident = build_incident_summary(jobs, now_ms)
    summary = {
        "jobCount": len(jobs),
        "enabledCount": sum(1 for job in jobs if job.get("enabled")),
        "healthyCount": sum(1 for job in jobs if job.get("status") == "healthy"),
        "pendingCount": sum(1 for job in jobs if job.get("status") == "pending"),
        "pausedCount": sum(1 for job in jobs if job.get("status") == "paused"),
        "warningCount": sum(1 for job in jobs if job.get("status") == "warning"),
        "criticalCount": sum(1 for job in jobs if job.get("status") == "critical"),
        "alertCount": len(alerts),
        "incidentCount": sum(1 for job in jobs if isinstance(job.get("incident"), dict)),
    }
    return {
        "checkedAt": _now_utc().isoformat().replace("+00:00", "Z"),
        "jobs": jobs,
        "alerts": alerts,
        "incident": incident,
        "summary": summary,
    }


if __name__ == "__main__":
    print(json.dumps(build_automation_snapshot(), ensure_ascii=False, indent=2))

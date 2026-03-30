#!/usr/bin/env python3
"""Generate a tech news brief from WallstreetCN tech live feed."""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any

from utils import beijing_now


WALLSTREET_TECH_URL = "https://wallstreetcn.com/live/tech"
WALLSTREET_API_URL = "https://api-one-wscn.awtmt.com/apiv1/content/lives"
WALLSTREET_TECH_CHANNEL = "tech-channel"
WALLSTREET_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": WALLSTREET_TECH_URL,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _fetch_wallstreet_tech_items(limit: int) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "channel": WALLSTREET_TECH_CHANNEL,
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


def _clean_html_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _build_summary(text: str, limit: int) -> str:
    clean = _clean_html_text(text)
    if not clean:
        return ""
    sentence = re.split(r"[。！？!?；;]", clean)[0].strip()
    base = sentence or clean
    return base[:limit].rstrip() + ("..." if len(base) > limit else "")


def _format_item(item: dict[str, Any], summary_limit: int) -> dict[str, Any]:
    item_id = str(item.get("id") or "")
    title = str(item.get("title") or "").strip()
    content = str(item.get("content") or "")
    display_time = item.get("display_time")

    if not title:
        title = _build_summary(content, 42) or "未命名快讯"

    timestamp = beijing_now()
    if isinstance(display_time, (int, float)) and display_time > 0:
        timestamp = datetime.fromtimestamp(float(display_time), tz=beijing_now().tzinfo)

    return {
        "id": item_id,
        "title": title,
        "summary": _build_summary(content, summary_limit),
        "link": str(item.get("uri") or (f"https://wallstreetcn.com/livenews/{item_id}" if item_id else WALLSTREET_TECH_URL)),
        "time": timestamp.strftime("%H:%M"),
        "timestamp": timestamp,
    }


def _filter_recent_items(items: list[dict[str, Any]], hours: int, limit: int) -> list[dict[str, Any]]:
    cutoff = beijing_now() - timedelta(hours=hours)
    recent = [item for item in items if item["timestamp"] >= cutoff]
    ordered = sorted(recent or items, key=lambda item: item["timestamp"], reverse=True)
    return ordered[:limit]


def _render_brief(items: list[dict[str, Any]]) -> str:
    now_text = beijing_now().strftime("%Y年%-m月%-d日 %H:%M")
    lines = [
        f"📰 科技新闻早晚播报 ({now_text})",
        "来源：华尔街见闻科技快讯",
        "",
    ]
    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                f"{index}. {item['title']}",
                f"概要：{item['summary'] or '暂无概要'}",
                f"链接：{item['link']}",
                "",
            ]
        )
    lines.append("---")
    lines.append("By AI Agent")
    return "\n".join(lines).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="WallstreetCN tech live brief")
    parser.add_argument("--hours", type=int, default=12, help="Only keep items within recent N hours")
    parser.add_argument("--limit", type=int, default=8, help="Maximum items to include")
    parser.add_argument("--summary-limit", type=int, default=88, help="Summary character limit")
    parser.add_argument("--json", action="store_true", help="Print parsed JSON instead of text brief")
    args = parser.parse_args()

    raw_items = _fetch_wallstreet_tech_items(limit=max(args.limit * 3, 24))
    parsed_items = [_format_item(item, args.summary_limit) for item in raw_items]
    selected_items = _filter_recent_items(parsed_items, args.hours, args.limit)

    if args.json:
        serializable = [
            {
                "id": item["id"],
                "title": item["title"],
                "summary": item["summary"],
                "link": item["link"],
                "time": item["time"],
            }
            for item in selected_items
        ]
        print(json.dumps({"count": len(serializable), "items": serializable}, ensure_ascii=False, indent=2))
        return 0

    print(_render_brief(selected_items))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

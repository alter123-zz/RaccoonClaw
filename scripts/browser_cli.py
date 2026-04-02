#!/usr/bin/env python3
"""Minimal browser-driven search/open helper for agent fallback research."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.parse import quote_plus

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_VIEWPORT = {"width": 1440, "height": 1100}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

SEARCH_ENGINES = {
    "bing": "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/html/?q={query}",
    "brave": "https://search.brave.com/search?q={query}&source=web",
}

SEARCH_SELECTORS = {
    "bing": [
        ("li.b_algo", "h2 a", ".b_caption p"),
        (".b_algo", "h2 a", ".b_caption p"),
    ],
    "duckduckgo": [
        (".result", "a.result__a", ".result__snippet"),
        (".web-result", "a.result__title", ".result__snippet"),
    ],
    "brave": [
        (".snippet", "a.heading-serpresult", ".snippet-description"),
        (".card[data-type='web']", "a", ".snippet-description"),
    ],
}

ENGINE_HOST_FILTERS = {
    "bing": ("bing.com", "microsoft.com"),
    "duckduckgo": ("duckduckgo.com",),
    "brave": ("search.brave.com", "brave.com"),
}


def _safe_text(locator) -> str:
    try:
        if locator.count() == 0:
            return ""
        return " ".join(locator.first.inner_text(timeout=2000).split())
    except Exception:
        return ""


def _safe_href(locator) -> str:
    try:
        if locator.count() == 0:
            return ""
        return str(locator.first.get_attribute("href") or "").strip()
    except Exception:
        return ""


def _extract_search_results(page, engine: str, limit: int) -> list[dict[str, str]]:
    selectors = SEARCH_SELECTORS.get(engine, [])
    for item_selector, title_selector, snippet_selector in selectors:
        cards = page.locator(item_selector)
        count = min(cards.count(), limit)
        results: list[dict[str, str]] = []
        for idx in range(count):
            card = cards.nth(idx)
            title_locator = card.locator(title_selector)
            title = _safe_text(title_locator)
            url = _safe_href(title_locator)
            if not title or not url:
                continue
            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": _safe_text(card.locator(snippet_selector)),
                }
            )
        if results:
            return results
    return []


def _extract_search_results_generic(page, engine: str, limit: int) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    blocked_hosts = ENGINE_HOST_FILTERS.get(engine, ())
    anchors = page.locator("a[href]")
    count = min(anchors.count(), 120)
    for idx in range(count):
        anchor = anchors.nth(idx)
        href = _safe_href(anchor)
        title = _safe_text(anchor)
        if not href or not title:
            continue
        if not href.startswith("http"):
            continue
        lowered_href = href.lower()
        if any(host in lowered_href for host in blocked_hosts):
            continue
        if title in seen:
            continue
        if len(title) < 4:
            continue
        seen.add(title)
        results.append({"title": title, "url": href, "snippet": ""})
        if len(results) >= limit:
            break
    return results


def run_search(query: str, engine: str, limit: int) -> dict[str, Any]:
    attempted: list[str] = []
    engines = [engine] if engine != "auto" else ["brave", "duckduckgo", "bing"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            user_agent=DEFAULT_USER_AGENT,
            locale="zh-CN",
        )
        page = context.new_page()
        try:
            for engine_name in engines:
                attempted.append(engine_name)
                url = SEARCH_ENGINES[engine_name].format(query=quote_plus(query))
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1500)
                    results = _extract_search_results(page, engine_name, limit)
                    if not results:
                        results = _extract_search_results_generic(page, engine_name, limit)
                    if results:
                        return {
                            "ok": True,
                            "mode": "search",
                            "query": query,
                            "engine": engine_name,
                            "attempted": attempted,
                            "results": results,
                        }
                except (PlaywrightTimeoutError, PlaywrightError) as exc:
                    last_error = f"{engine_name}: {exc}"
                    continue
        finally:
            browser.close()

    return {
        "ok": False,
        "mode": "search",
        "query": query,
        "engine": engine,
        "attempted": attempted,
        "error": locals().get("last_error", "no_results"),
    }


def run_open(url: str, max_chars: int) -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            user_agent=DEFAULT_USER_AGENT,
            locale="zh-CN",
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(1000)
            body_text = page.locator("body").inner_text(timeout=5000)
            body_text = " ".join(body_text.split())
            return {
                "ok": True,
                "mode": "open",
                "url": url,
                "title": page.title(),
                "text": body_text[:max_chars],
            }
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            return {
                "ok": False,
                "mode": "open",
                "url": url,
                "error": str(exc),
            }
        finally:
            browser.close()


def _print_human(payload: dict[str, Any]) -> None:
    if not payload.get("ok"):
        print(f"ERROR: {payload.get('error', 'unknown_error')}")
        return
    if payload.get("mode") == "search":
        print(f"# Search: {payload['query']}")
        print(f"# Engine: {payload['engine']}")
        for idx, item in enumerate(payload.get("results") or [], start=1):
            print(f"{idx}. {item['title']}")
            print(f"   URL: {item['url']}")
            if item.get("snippet"):
                print(f"   Snippet: {item['snippet']}")
    else:
        print(f"# Title: {payload.get('title', '')}")
        print(f"# URL: {payload['url']}")
        print(payload.get("text", ""))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Browser CLI fallback for research tasks")
    sub = parser.add_subparsers(dest="command", required=True)

    search_parser = sub.add_parser("search", help="Search the web using a real browser")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--engine", choices=("auto", "bing", "duckduckgo", "brave"), default="auto")
    search_parser.add_argument("--limit", type=int, default=5)
    search_parser.add_argument("--json", action="store_true")

    open_parser = sub.add_parser("open", help="Open a page and extract body text")
    open_parser.add_argument("url", help="URL to open")
    open_parser.add_argument("--max-chars", type=int, default=6000)
    open_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv[1:])

    if args.command == "search":
        payload = run_search(args.query, args.engine, max(1, args.limit))
    else:
        payload = run_open(args.url, max(500, args.max_chars))

    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_human(payload)
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

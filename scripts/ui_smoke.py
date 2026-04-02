#!/usr/bin/env python3
"""Browser smoke checks for the workbench UI.

This script intentionally targets a running local dashboard instance and
verifies the highest-value user paths that previously regressed:

1. Chat attachment upload/remove.
2. Task launch page scheduled cards do not show automation mirror ids.
3. Memorial search can find and filter archived tasks by id.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


BASE_URL = os.environ.get("WORKBENCH_UI_SMOKE_URL", "http://127.0.0.1:7891").rstrip("/")
TASK_ID_RE = re.compile(r"(?:JJC|D|L|F)-\d{8}-\d{3}")


def _wait(page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)


def _open_sidebar(page, label: str) -> None:
    page.get_by_role("button", name=label).first.click()
    _wait(page)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _chat_attachment_smoke(page) -> dict:
    _open_sidebar(page, "对话")
    attach_btn = page.locator(".chat-attach-btn")
    _assert(attach_btn.count() == 1 and attach_btn.first.is_visible(), "chat attachment button missing")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "ui-smoke-attachment.txt"
        path.write_text("ui smoke attachment\n", encoding="utf-8")
        page.locator("input.chat-file-input").nth(0).set_input_files(str(path))
        page.wait_for_timeout(800)
        pending = page.locator(".chat-pending-attachment")
        _assert(pending.count() >= 1, "pending attachment chip not rendered after upload")
        _assert(path.name in pending.first.inner_text(), "uploaded attachment name not visible in pending chip")
        page.locator(".chat-pending-attachment-remove").first.click()
        page.wait_for_timeout(500)
        remaining = page.locator(".chat-pending-attachment", has_text=path.name)
        _assert(remaining.count() == 0, "attachment chip still visible after remove")
    return {"chatAttachment": "ok"}


def _scheduled_cards_smoke(page) -> dict:
    _open_sidebar(page, "发起任务")
    cards = page.locator(".launch-scheduled-card")
    texts = [cards.nth(i).inner_text() for i in range(cards.count())]
    _assert(all("JJC-AUTO-" not in text for text in texts), "automation mirror id leaked into scheduled task cards")
    return {"scheduledCards": {"count": len(texts), "mirrorIdsHidden": True}}


def _memorial_search_smoke(page) -> dict:
    _open_sidebar(page, "交付归档")
    cards = page.locator(".mem-card")
    _assert(cards.count() >= 1, "no memorial cards available for search smoke")
    first_meta = cards.first.locator(".mem-card-meta").inner_text()
    match = TASK_ID_RE.search(first_meta)
    _assert(match is not None, "could not extract task id from memorial card")
    task_id = match.group(0)

    search = page.locator(".mem-search input")
    _assert(search.count() == 1, "memorial search input missing")
    search.fill(task_id)
    page.wait_for_timeout(300)

    filtered = page.locator(".mem-card")
    _assert(filtered.count() >= 1, "memorial search filtered out the target task")
    for i in range(filtered.count()):
        text = filtered.nth(i).inner_text()
        _assert(task_id in text, f"memorial search returned unrelated card for query {task_id}")
    return {"memorialSearch": {"query": task_id, "count": filtered.count()}}


def main() -> int:
    results: dict[str, object] = {"baseUrl": BASE_URL}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1600, "height": 1200})
            page = context.new_page()
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
            _wait(page)
            results.update(_chat_attachment_smoke(page))
            results.update(_scheduled_cards_smoke(page))
            results.update(_memorial_search_smoke(page))
            context.close()
            browser.close()
    except PlaywrightTimeoutError as exc:
        print(json.dumps({"ok": False, "error": f"timeout: {exc}", **results}, ensure_ascii=False))
        return 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), **results}, ensure_ascii=False))
        return 1

    print(json.dumps({"ok": True, **results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

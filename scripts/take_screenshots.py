#!/usr/bin/env python3
"""Take dashboard screenshots for the README using Playwright.

Assumes the backend is already running on http://127.0.0.1:7891.
"""

from __future__ import annotations

import os
from typing import Iterable, Tuple

from playwright.sync_api import sync_playwright

SHOTS = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots")
URL = os.environ.get("RACCOONCLAW_SHOT_URL", "http://127.0.0.1:7891")

SHOT_DEFS: Tuple[Tuple[str, str, str], ...] = (
    ("01-chat.png", "对话", "💬"),
    ("02-overview.png", "概览", "🏠"),
    ("03-godview.png", "状态监控", "📡"),
    ("04-kanban.png", "任务看板", "📋"),
    ("05-templates.png", "模板库", "🧩"),
    ("06-officials.png", "团队总览", "👥"),
    ("07-models.png", "模型配置", "🤖"),
    ("08-skills.png", "技能配置", "🎯"),
    ("09-toolbox.png", "百宝箱", "🧰"),
    ("10-memorials.png", "交付归档", "📦"),
)


def _stabilize(page) -> None:
    page.wait_for_load_state("networkidle")
    # Avoid transient animations/toasts causing diffs.
    page.wait_for_timeout(1500)


def click_sidebar_tab(page, label: str) -> None:
    page.locator("button.workspace-sidebar-link", has_text=label).first.click()
    _stabilize(page)


def take_shell_shot(page, out_path: str) -> None:
    page.locator(".enterprise-shell").screenshot(path=out_path)


def main() -> None:
    os.makedirs(SHOTS, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1720, "height": 1180},
            device_scale_factor=2,
        )
        page = ctx.new_page()

        page.goto(URL)
        _stabilize(page)

        for fname, label, icon in SHOT_DEFS:
            print(f"{icon} {fname} -> {label} ...")
            click_sidebar_tab(page, label)
            take_shell_shot(page, os.path.join(SHOTS, fname))

        browser.close()

    print("✅ All screenshots saved to", SHOTS)


if __name__ == "__main__":
    main()

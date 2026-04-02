#!/usr/bin/env python3
"""Helpers for OpenClaw workbench task ids."""

from __future__ import annotations

import datetime as dt
import re
from typing import Iterable


NORMAL_TASK_ID_PATTERN = r"(?:JJC|D|L|F)-\d{8}-\d{3}"
AUTOMATION_TASK_ID_PATTERN = r"JJC-AUTO-[A-Z0-9]+"
TASK_ID_PATTERN = rf"(?:{NORMAL_TASK_ID_PATTERN}|{AUTOMATION_TASK_ID_PATTERN})"
_ID_LEFT_BOUNDARY = r"(?<![A-Za-z0-9])"
_ID_RIGHT_BOUNDARY = r"(?![A-Za-z0-9])"
NORMAL_TASK_ID_RE = re.compile(rf"{_ID_LEFT_BOUNDARY}{NORMAL_TASK_ID_PATTERN}{_ID_RIGHT_BOUNDARY}", flags=re.IGNORECASE)
TASK_ID_RE = re.compile(rf"{_ID_LEFT_BOUNDARY}{TASK_ID_PATTERN}{_ID_RIGHT_BOUNDARY}", flags=re.IGNORECASE)

FLOW_PREFIX_MAP = {
    "direct": "D",
    "light": "L",
    "full": "F",
}


def normalize_flow_mode(flow_mode: str | None) -> str:
    value = str(flow_mode or "").strip().lower()
    if value == "chief_direct":
        value = "direct"
    return value if value in FLOW_PREFIX_MAP else "full"


def task_prefix_for_flow_mode(flow_mode: str | None) -> str:
    return FLOW_PREFIX_MAP[normalize_flow_mode(flow_mode)]


def is_normal_task_id(task_id: str | None) -> bool:
    return bool(NORMAL_TASK_ID_RE.fullmatch(str(task_id or "").strip()))


def next_task_id(now: dt.datetime, flow_mode: str | None, existing_ids: Iterable[str]) -> str:
    prefix = task_prefix_for_flow_mode(flow_mode)
    day = now.strftime("%Y%m%d")
    day_prefix = f"{prefix}-{day}-"
    max_seq = 0
    for raw in existing_ids:
        task_id = str(raw or "").strip()
        if not task_id.startswith(day_prefix):
            continue
        try:
            seq = int(task_id.split("-")[-1])
        except Exception:
            continue
        max_seq = max(max_seq, seq)
    return f"{day_prefix}{max_seq + 1:03d}"

#!/usr/bin/env python3
"""Shared workbench mode helpers for backend/runtime scripts."""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from functools import lru_cache
from typing import Any


def _resolve_shared_root() -> pathlib.Path:
    project_root = str(os.environ.get("OPENCLAW_PROJECT_ROOT", "")).strip()
    if project_root:
        return pathlib.Path(project_root).expanduser() / "shared"
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return pathlib.Path(sys._MEIPASS) / "shared"
    return pathlib.Path(__file__).resolve().parent.parent / "shared"


WORKBENCH_MODES_PATH = _resolve_shared_root() / "workbench-modes.json"

_CONTENT_CREATION_PATTERNS = [
    r"写(?:一篇|成|作|稿|文章)?",
    r"扩写",
    r"改写",
    r"润色",
    r"成稿",
    r"博客",
    r"公众号",
    r"推文",
    r"文案",
    r"稿件",
    r"文章",
    r"标题",
    r"大纲",
    r"选题",
    r"深度稿",
]
_CONTENT_CREATION_DEPTS = {"品牌内容部"}


@lru_cache(maxsize=1)
def load_workbench_modes() -> list[dict[str, Any]]:
    return json.loads(WORKBENCH_MODES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def workbench_mode_map() -> dict[str, dict[str, Any]]:
    return {str(mode["key"]): mode for mode in load_workbench_modes()}


def normalize_mode_id(raw: Any) -> str | None:
    value = str(raw or "").strip()
    if not value or value == "all":
        return None
    return value if value in workbench_mode_map() else None


def default_target_dept_for_mode(mode_id: Any) -> str:
    normalized = normalize_mode_id(mode_id)
    if not normalized:
        return ""
    mode = workbench_mode_map().get(normalized) or {}
    return str(mode.get("defaultTargetDept") or "").strip()


def _template_mode_id(template_id: str) -> str | None:
    normalized = str(template_id or "").strip()
    if not normalized:
        return None
    for mode in load_workbench_modes():
        if str(mode.get("key")) == "all":
            continue
        if normalized in mode.get("templateIds", []):
            return str(mode["key"])
    return None


def _specialist_mode_id(target_dept: str = "", org: str = "", flow_log: list[dict[str, Any]] | None = None) -> str | None:
    flow_log = flow_log or []
    target = str(target_dept or "").strip()
    current_org = str(org or "").strip()
    for mode in load_workbench_modes():
        mode_key = str(mode.get("key"))
        if mode_key == "all":
            continue
        specialist = set(mode.get("specialistDepts", []))
        if target in specialist or current_org in specialist:
            return mode_key
        for entry in flow_log:
            if str(entry.get("from", "")).strip() in specialist or str(entry.get("to", "")).strip() in specialist:
                return mode_key
    return None


def _content_creation_mode_id(
    title: str = "",
    template_id: str = "",
    target_dept: str = "",
    params: dict[str, Any] | None = None,
) -> str | None:
    params = params if isinstance(params, dict) else {}
    if str(target_dept or "").strip() in _CONTENT_CREATION_DEPTS:
        return "content_creation"

    values: list[str] = [str(title or ""), str(template_id or "")]
    for value in params.values():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            values.extend(str(item) for item in value if item)
            continue
        values.append(str(value))
    haystack = re.sub(r"\s+", " ", " ".join(values)).strip().lower()
    if not haystack:
        return None
    for pattern in _CONTENT_CREATION_PATTERNS:
        if re.search(pattern, haystack, re.IGNORECASE):
            return "content_creation"
    return None


def infer_mode_id_for_task(task: dict[str, Any]) -> str | None:
    template_params = task.get("templateParams")
    if not isinstance(template_params, dict):
        template_params = {}
    source_meta = task.get("sourceMeta")
    if not isinstance(source_meta, dict):
        source_meta = {}

    explicit = normalize_mode_id(
        task.get("modeId")
        or template_params.get("modeId")
        or template_params.get("workbenchMode")
        or source_meta.get("modeId")
        or source_meta.get("workbenchMode")
    )
    if explicit:
        return explicit

    by_template = _template_mode_id(str(task.get("templateId", "")).strip())
    if by_template:
        return by_template

    return _specialist_mode_id(
        target_dept=str(task.get("targetDept", "")).strip(),
        org=str(task.get("org", "")).strip(),
        flow_log=task.get("flow_log") if isinstance(task.get("flow_log"), list) else [],
    )


def resolve_mode_id_for_create(mode_id: Any = "", template_id: Any = "", target_dept: Any = "", params: dict[str, Any] | None = None) -> str | None:
    params = params if isinstance(params, dict) else {}
    explicit = normalize_mode_id(mode_id or params.get("modeId") or params.get("workbenchMode"))
    if explicit:
        return explicit

    by_template = _template_mode_id(str(template_id or "").strip())
    if by_template:
        return by_template

    semantic = _content_creation_mode_id(
        title=str((params or {}).get("title") or ""),
        template_id=str(template_id or "").strip(),
        target_dept=str(target_dept or "").strip(),
        params=params,
    )
    if semantic:
        return semantic

    return _specialist_mode_id(target_dept=str(target_dept or "").strip())


def inject_mode_id(task: dict[str, Any]) -> dict[str, Any]:
    mode_id = infer_mode_id_for_task(task)
    if not mode_id:
        return task

    task["modeId"] = mode_id
    source_meta = task.get("sourceMeta")
    if not isinstance(source_meta, dict):
        source_meta = {}
    source_meta.setdefault("modeId", mode_id)
    task["sourceMeta"] = source_meta
    return task

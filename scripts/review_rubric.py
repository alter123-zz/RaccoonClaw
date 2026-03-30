#!/usr/bin/env python3
"""Shared review rubric resolver for Menxia and the workbench UI."""

from __future__ import annotations

import argparse
import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from runtime_paths import canonical_data_dir
from workbench_modes import infer_mode_id_for_task, normalize_mode_id


ROOT = Path(__file__).resolve().parent.parent
RUBRIC_PATH = ROOT / "shared" / "review-rubric.json"
TASKS_PATH = canonical_data_dir() / "tasks_source.json"


def _clean(value: Any) -> str:
    return str(value or "").strip()


@lru_cache(maxsize=1)
def load_review_rubric() -> dict[str, Any]:
    return json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))


def _check_map() -> dict[str, dict[str, Any]]:
    config = load_review_rubric()
    return {
        str(item["key"]): item
        for item in config.get("checks", [])
        if isinstance(item, dict) and item.get("key")
    }


def _level_map() -> dict[str, dict[str, Any]]:
    config = load_review_rubric()
    return {
        str(item["key"]): item
        for item in config.get("findingLevels", [])
        if isinstance(item, dict) and item.get("key")
    }


def _task_map() -> dict[str, dict[str, Any]]:
    try:
        tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    except Exception:
        tasks = []
    return {
        str(task.get("id")): task
        for task in tasks
        if isinstance(task, dict) and task.get("id")
    }


def find_task(task_id: str) -> dict[str, Any] | None:
    return _task_map().get(_clean(task_id))


def _dynamic_checks(requirement: str) -> list[str]:
    requirement_lower = requirement.lower()
    config = load_review_rubric()
    selected: list[str] = []
    for item in config.get("dynamicSignals", []):
        if not isinstance(item, dict):
            continue
        signals = [str(value).lower() for value in item.get("match", []) if str(value).strip()]
        if not signals:
            continue
        if any(signal in requirement_lower for signal in signals):
            selected.extend(str(value) for value in item.get("addChecks", []) if str(value).strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for key in selected:
        if key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped


def resolve_profile(mode_id: str | None = None, requirement: str = "") -> dict[str, Any]:
    config = load_review_rubric()
    profiles = config.get("profiles", {})
    raw_mode = _clean(mode_id)
    profile_key = raw_mode if raw_mode == "all" else (normalize_mode_id(raw_mode) or "default")
    base = copy.deepcopy(profiles.get("default", {}))
    if profile_key != "default":
        override = profiles.get(profile_key, {})
        base.update(copy.deepcopy(override))
    base.setdefault("label", "通用评审")
    base.setdefault("requiredChecks", [])
    base.setdefault("readinessChecks", base.get("requiredChecks", []))
    base.setdefault("focus", [])

    required = list(base.get("requiredChecks", []))
    readiness = list(base.get("readinessChecks", []))
    for key in _dynamic_checks(requirement):
        if key not in required:
            required.append(key)
        if key in {"security", "testing", "delivery"} and key not in readiness:
            readiness.append(key)

    checks = _check_map()
    base["key"] = profile_key
    base["requiredChecks"] = [key for key in required if key in checks]
    base["readinessChecks"] = [key for key in readiness if key in checks]
    base["checkDetails"] = [checks[key] for key in base["requiredChecks"]]
    base["readinessDetails"] = [checks[key] for key in base["readinessChecks"]]
    base["findingLevels"] = list(_level_map().values())
    return base


def evaluate_plan(plan_text: str, mode_id: str | None = None, requirement: str = "") -> dict[str, Any]:
    profile = resolve_profile(mode_id, requirement)
    plan_lower = _clean(plan_text).lower()
    missing: list[dict[str, Any]] = []
    for item in profile.get("readinessDetails", []):
        aliases = [str(value).lower() for value in item.get("aliases", []) if str(value).strip()]
        if aliases and any(alias in plan_lower for alias in aliases):
            continue
        missing.append(
            {
                "key": item["key"],
                "label": item["label"],
                "severity": "blocker",
                "message": f"缺少“{item['label']}”相关说明：{item['prompt']}",
            }
        )
    return {
        "ok": not missing,
        "profile": profile,
        "missingFindings": missing,
    }


def build_brief(mode_id: str | None = None, requirement: str = "") -> dict[str, Any]:
    profile = resolve_profile(mode_id, requirement)
    return {
        "profileKey": profile["key"],
        "profileLabel": profile["label"],
        "focus": profile.get("focus", []),
        "requiredChecks": [
            {
                "key": item["key"],
                "label": item["label"],
                "prompt": item["prompt"],
            }
            for item in profile.get("checkDetails", [])
        ],
        "readinessChecks": [
            {
                "key": item["key"],
                "label": item["label"],
                "prompt": item["prompt"],
            }
            for item in profile.get("readinessDetails", [])
        ],
        "findingLevels": profile.get("findingLevels", []),
    }


def _markdown_brief(payload: dict[str, Any]) -> str:
    profile_label = payload.get("profileLabel") or payload.get("label") or "通用评审"
    checks = payload.get("requiredChecks") or payload.get("checkDetails") or []
    lines = [
        f"评审画像：{profile_label}",
        "结论等级：",
    ]
    for item in payload.get("findingLevels", []):
        lines.append(f"- [{item['key']}] {item['label']}：{item['description']}（{item['decision']}）")
    lines.append("必查项：")
    for item in checks:
        lines.append(f"- {item['label']}：{item['prompt']}")
    if payload.get("focus"):
        lines.append("重点关注：")
        for item in payload["focus"]:
            lines.append(f"- {item}")
    lines.append("输出格式：")
    lines.append("- [blocker] 问题描述")
    lines.append("- [suggestion] 优化建议")
    lines.append("- [nit] 细节优化")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve review rubric for a mode or task")
    parser.add_argument("--task-id", help="Existing task id")
    parser.add_argument("--mode-id", help="Workbench mode id")
    parser.add_argument("--requirement", help="Requirement/title text")
    parser.add_argument("--plan", help="Plan text to evaluate against readiness checks")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args(argv)

    task = find_task(args.task_id) if args.task_id else None
    requirement = _clean(args.requirement) or _clean(task.get("title") if task else "")
    mode_id = _clean(args.mode_id) or (infer_mode_id_for_task(task) if task else None)

    payload = evaluate_plan(args.plan, mode_id, requirement) if args.plan else build_brief(mode_id, requirement)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_markdown_brief(payload["profile"] if "profile" in payload else payload))
    return 0 if not args.plan or payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())

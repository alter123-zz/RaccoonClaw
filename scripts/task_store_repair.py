#!/usr/bin/env python3
"""Repair historical task records into the current canonical runtime contract."""

from __future__ import annotations

import datetime
import logging
import pathlib
import re
import shutil

from file_lock import atomic_json_read, atomic_json_update, atomic_json_write
from runtime_paths import (
    candidate_deliverables_roots,
    canonical_data_dir,
    canonical_task_deliverables_dir,
    openclaw_home,
)
from task_ids import NORMAL_TASK_ID_RE


log = logging.getLogger("task_store_repair")

TASKS_FILE = canonical_data_dir() / "tasks_source.json"
REPORT_FILE = canonical_data_dir() / "task_store_repair_report.json"
OCLAW_HOME = openclaw_home()
ARTIFACT_DIR_NAMES = ("deliverables", "reports", "outputs", "artifacts")
CALLBACK_TODO_KEYWORDS = ("回传总裁办", "结果回传", "回传需求方", "回传")
STALE_DONE_TEXT_RE = re.compile(r"(整理摘要并回传总裁办|收到专项团队执行结果|执行完成)")
MISSING_OUTPUT_SUMMARY = "历史任务缺少真实交付物，需重新回传"


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _task_id(raw: object) -> str:
    return str(raw or "").strip()


def _iter_task_artifacts(task: dict) -> list[pathlib.Path]:
    task_id = _task_id(task.get("id"))
    if not task_id:
        return []

    candidates: list[pathlib.Path] = []
    seen: set[str] = set()

    def add(path_like: pathlib.Path | str | None) -> None:
        if not path_like:
            return
        path = pathlib.Path(path_like).expanduser()
        key = str(path)
        if key in seen:
            return
        seen.add(key)
        if path.exists() and path.is_file():
            candidates.append(path)

    add(str(task.get("output") or "").strip() or None)

    for root in candidate_deliverables_roots():
        task_dir = root / task_id
        if task_dir.is_dir():
            for path in sorted(task_dir.rglob("*")):
                if path.is_file():
                    add(path)

    for workspace in OCLAW_HOME.glob("workspace-*"):
        for folder_name in ARTIFACT_DIR_NAMES:
            folder = workspace / folder_name
            if not folder.exists():
                continue
            for path in folder.rglob("*"):
                if not path.is_file():
                    continue
                match = NORMAL_TASK_ID_RE.search(path.name)
                if match and match.group(0) == task_id:
                    add(path)

    candidates.sort(
        key=lambda path: (
            1 if canonical_task_deliverables_dir(task_id) in path.parents else 0,
            path.stat().st_mtime,
            len(path.name),
        ),
        reverse=True,
    )
    return candidates


def _canonicalize_artifact(task_id: str, source: pathlib.Path) -> pathlib.Path:
    target_dir = canonical_task_deliverables_dir(task_id)
    target = target_dir / source.name
    if target.exists():
        return target
    shutil.copy2(source, target)
    return target


def _mark_callback_completed(task: dict) -> bool:
    changed = False
    todos = task.get("todos")
    if not isinstance(todos, list):
        return False
    for item in todos:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title or not any(keyword in title for keyword in CALLBACK_TODO_KEYWORDS):
            continue
        if item.get("status") != "completed":
            item["status"] = "completed"
            changed = True
        detail = str(item.get("detail") or "").strip()
        if not detail:
            item["detail"] = "历史任务启动自修复：已补齐真实交付文件并完成回传。"
            changed = True
    return changed


def _repair_done_task(task: dict, best_artifact: pathlib.Path | None) -> bool:
    changed = False
    if best_artifact is None:
        if task.get("state") == "Done":
            task["state"] = "Blocked"
            task["org"] = "总裁办"
            task["block"] = MISSING_OUTPUT_SUMMARY
            task["now"] = MISSING_OUTPUT_SUMMARY
            changed = True
        return changed

    task_id = _task_id(task.get("id"))
    canonical_artifact = _canonicalize_artifact(task_id, best_artifact)
    canonical_path = str(canonical_artifact)
    if str(task.get("output") or "").strip() != canonical_path:
        task["output"] = canonical_path
        changed = True
    if task.get("block") not in ("", "无"):
        task["block"] = ""
        changed = True
    if _mark_callback_completed(task):
        changed = True
    now_text = str(task.get("now") or "").strip()
    if not now_text or STALE_DONE_TEXT_RE.search(now_text):
        task["now"] = "已完成：回传总裁办"
        changed = True
    if task.get("org") != "完成":
        task["org"] = "完成"
        changed = True
    return changed


def repair_task_store(tasks_file: pathlib.Path | None = None, report_file: pathlib.Path | None = None) -> dict[str, object]:
    target = tasks_file or TASKS_FILE
    if not target.exists():
        stats: dict[str, object] = {
            "generatedAt": now_iso(),
            "scanned": 0,
            "changed": 0,
            "migratedOutputs": 0,
            "blockedTasks": 0,
            "changedTaskIds": [],
            "migratedTaskIds": [],
            "blockedTaskIds": [],
        }
        atomic_json_write(report_file or REPORT_FILE, stats)
        return stats

    stats: dict[str, object] = {
        "generatedAt": now_iso(),
        "scanned": 0,
        "changed": 0,
        "migratedOutputs": 0,
        "blockedTasks": 0,
        "changedTaskIds": [],
        "migratedTaskIds": [],
        "blockedTaskIds": [],
    }

    def modifier(tasks: list[dict]) -> list[dict]:
        if not isinstance(tasks, list):
            return tasks
        for task in tasks:
            if not isinstance(task, dict):
                continue
            stats["scanned"] = int(stats["scanned"]) + 1
            before_output = str(task.get("output") or "").strip()
            before_state = str(task.get("state") or "").strip()
            task_id = _task_id(task.get("id"))
            best_artifact = _iter_task_artifacts(task)[:1]
            changed = False
            if before_state == "Done":
                changed = _repair_done_task(task, best_artifact[0] if best_artifact else None)
            elif best_artifact:
                canonical_artifact = _canonicalize_artifact(task_id, best_artifact[0])
                canonical_path = str(canonical_artifact)
                if before_output and before_output != canonical_path and pathlib.Path(before_output).exists():
                    task["output"] = canonical_path
                    changed = True
            if changed:
                task["updatedAt"] = now_iso()
                stats["changed"] = int(stats["changed"]) + 1
                changed_ids = stats["changedTaskIds"]
                if isinstance(changed_ids, list) and task_id:
                    changed_ids.append(task_id)
                if str(task.get("output") or "").strip() and str(task.get("output") or "").strip() != before_output:
                    stats["migratedOutputs"] = int(stats["migratedOutputs"]) + 1
                    migrated_ids = stats["migratedTaskIds"]
                    if isinstance(migrated_ids, list) and task_id:
                        migrated_ids.append(task_id)
                if before_state != str(task.get("state") or "").strip() and task.get("state") == "Blocked":
                    stats["blockedTasks"] = int(stats["blockedTasks"]) + 1
                    blocked_ids = stats["blockedTaskIds"]
                    if isinstance(blocked_ids, list) and task_id:
                        blocked_ids.append(task_id)
        return tasks

    atomic_json_update(target, modifier, [])
    atomic_json_write(report_file or REPORT_FILE, stats)
    return stats


def main() -> None:
    stats = repair_task_store()
    log.info(
        "repaired task store scanned=%s changed=%s migrated_outputs=%s blocked=%s",
        stats["scanned"],
        stats["changed"],
        stats["migratedOutputs"],
        stats["blockedTasks"],
    )


if __name__ == "__main__":
    main()

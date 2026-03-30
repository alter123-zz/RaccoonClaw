#!/usr/bin/env python3
"""Render structured blocker feedback for a given task id."""

from __future__ import annotations

import argparse
import json
import sys

from blocker_utils import render_blocker_feedback, summarize_task_blocker
from runtime_paths import canonical_data_dir


def load_tasks() -> list[dict]:
    path = canonical_data_dir() / "tasks_source.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else payload.get("tasks", [])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Render structured blocker feedback for a task")
    parser.add_argument("task_id", help="Task id like JJC-20260314-003")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    args = parser.parse_args(argv[1:])

    tasks = load_tasks()
    task = next((item for item in tasks if str(item.get("id") or "") == args.task_id), None)
    if task is None:
        print(f"任务 {args.task_id} 不存在", file=sys.stderr)
        return 2

    report = summarize_task_blocker(task)
    if args.json:
        print(json.dumps({
            "taskId": args.task_id,
            "report": report,
            "feedback": render_blocker_feedback(task),
        }, ensure_ascii=False))
    else:
        print(render_blocker_feedback(task))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

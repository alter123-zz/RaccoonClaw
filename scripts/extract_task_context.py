#!/usr/bin/env python3
"""Extract and validate the exact workbench task id from a delegated message."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from runtime_paths import canonical_data_dir
from task_ids import NORMAL_TASK_ID_RE


def load_tasks() -> list[dict]:
    path = canonical_data_dir() / "tasks_source.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return raw if isinstance(raw, list) else raw.get("tasks", [])


def extract_title(message: str) -> str:
    for prefix in ("任务:", "任务：", "方案:", "方案：", "需求方原话:", "需求方原话："):
        for line in message.splitlines():
            line = line.strip()
            if line.startswith(prefix):
                return line.split(prefix, 1)[1].strip()
    return ""


def _task_attachments(task: dict) -> list[dict]:
    for key in ("templateParams", "sourceMeta"):
        payload = task.get(key)
        if isinstance(payload, dict):
            attachments = payload.get("chatAttachments")
            if isinstance(attachments, list):
                normalized = []
                for item in attachments:
                    if not isinstance(item, dict):
                        continue
                    normalized.append(
                        {
                            "id": str(item.get("id") or "").strip(),
                            "name": str(item.get("name") or "").strip(),
                            "path": str(item.get("path") or "").strip(),
                            "textExcerpt": str(item.get("textExcerpt") or "").strip(),
                        }
                    )
                if normalized:
                    return normalized
    return []


def _attachment_summary_lines(task: dict, limit: int = 2) -> list[str]:
    attachments = _task_attachments(task)
    lines: list[str] = []
    for item in attachments[:limit]:
        label = item.get("name") or pathlib.Path(item.get("path") or "").name or "未命名文件"
        lines.append(f"ATTACHMENT_NAME={label}")
        if item.get("path"):
            lines.append(f"ATTACHMENT_PATH={item['path']}")
        excerpt = (item.get("textExcerpt") or "").replace("\r", " ").replace("\n", "\\n").strip()
        if excerpt:
            lines.append(f"ATTACHMENT_EXCERPT={excerpt[:1200]}")
    if len(attachments) > limit:
        lines.append(f"ATTACHMENT_MORE={len(attachments) - limit}")
    return lines


def _user_brief(task: dict) -> str:
    for key in ("templateParams", "sourceMeta"):
        payload = task.get(key)
        if not isinstance(payload, dict):
            continue
        brief = str(payload.get("userBrief") or payload.get("rawRequest") or "").strip()
        if brief:
            return brief
    return ""


def _source_meta(task: dict) -> dict:
    payload = task.get("sourceMeta")
    return payload if isinstance(payload, dict) else {}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extract an exact workbench task id from text")
    parser.add_argument("message", help="Delegated message body that should contain one task id")
    parser.add_argument("--require-existing", action="store_true", help="Fail if the task does not exist yet")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of shell-style lines")
    args = parser.parse_args(argv[1:])

    ids = sorted(set(NORMAL_TASK_ID_RE.findall(args.message or "")))
    if len(ids) != 1:
        if len(ids) == 0:
            print("未找到任务ID（期望格式: D/L/F-YYYYMMDD-NNN，兼容 JJC-YYYYMMDD-NNN）", file=sys.stderr)
        else:
            print(f"发现多个任务ID，无法确定唯一上下文: {', '.join(ids)}", file=sys.stderr)
        return 2

    task_id = ids[0]
    tasks = load_tasks()
    task = next((item for item in tasks if item.get("id") == task_id), None)
    if args.require_existing and task is None:
        print(f"任务 {task_id} 不存在，禁止继续派发", file=sys.stderr)
        return 3

    payload = {
        "taskId": task_id,
        "exists": task is not None,
        "title": (task or {}).get("title") or extract_title(args.message),
        "state": (task or {}).get("state", ""),
        "org": (task or {}).get("org", ""),
        "targetDept": (task or {}).get("targetDept", ""),
        "modeId": (task or {}).get("modeId", ""),
        "flowMode": _source_meta(task or {}).get("flowMode", "") if task else "",
        "routeMode": _source_meta(task or {}).get("routeMode", "") if task else "",
        "dispatchOrg": _source_meta(task or {}).get("dispatchOrg", "") if task else "",
        "dispatchAgent": _source_meta(task or {}).get("dispatchAgent", "") if task else "",
        "requiredStages": _source_meta(task or {}).get("requiredStages", []) if task else [],
        "skipPlanning": bool(_source_meta(task or {}).get("skipPlanning")) if task else False,
        "skipReview": bool(_source_meta(task or {}).get("skipReview")) if task else False,
        "userBrief": _user_brief(task or {}) if task else "",
        "attachments": _task_attachments(task or {}) if task else [],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"TASK_ID={payload['taskId']}")
        print(f"TASK_EXISTS={'true' if payload['exists'] else 'false'}")
        if payload["title"]:
            print(f"TASK_TITLE={payload['title']}")
        if payload["state"]:
            print(f"TASK_STATE={payload['state']}")
        if payload["org"]:
            print(f"TASK_ORG={payload['org']}")
        if payload["targetDept"]:
            print(f"TASK_TARGET_DEPT={payload['targetDept']}")
        if payload["modeId"]:
            print(f"TASK_MODE_ID={payload['modeId']}")
        if payload["flowMode"]:
            print(f"TASK_FLOW_MODE={payload['flowMode']}")
        if payload["routeMode"]:
            print(f"TASK_ROUTE_MODE={payload['routeMode']}")
        if payload["dispatchOrg"]:
            print(f"TASK_DISPATCH_ORG={payload['dispatchOrg']}")
        if payload["dispatchAgent"]:
            print(f"TASK_DISPATCH_AGENT={payload['dispatchAgent']}")
        if payload["requiredStages"]:
            print("TASK_REQUIRED_STAGES=" + ",".join(str(item).strip() for item in payload["requiredStages"] if str(item).strip()))
        print(f"TASK_SKIP_PLANNING={'true' if payload['skipPlanning'] else 'false'}")
        print(f"TASK_SKIP_REVIEW={'true' if payload['skipReview'] else 'false'}")
        if payload["userBrief"]:
            brief = payload["userBrief"].replace("\r", " ").replace("\n", "\\n")
            print(f"TASK_USER_BRIEF={brief[:1800]}")
        if payload["attachments"]:
            print(f"TASK_ATTACHMENT_COUNT={len(payload['attachments'])}")
            for line in _attachment_summary_lines(task or {}):
                print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

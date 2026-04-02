#!/usr/bin/env python3
"""Delegate work to another OpenClaw agent via the local CLI.

For task-bearing messages, the delegate call is pinned to a deterministic
session id derived from ``agent_id + task id`` so different tasks do not
bleed into the same subagent conversation.

When --kanban-id is provided, automatically creates and updates kanban entries
so that all delegations are visible in the RaccoonClaw workbench.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from task_ids import NORMAL_TASK_ID_RE

DIRECT_TASK_MARKERS = ("⚡ 直派任务", "⚡ 直办任务", "直办任务")
SESSION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "openclaw-workbench/task-session")
OPENCLAW_HOME = Path.home() / ".openclaw"
AGENTS_ROOT = OPENCLAW_HOME / "agents"

# Path to this script's directory (for finding kanban_update.py)
SCRIPT_DIR = Path(__file__).resolve().parent

AGENT_LABELS = {
    "chief_of_staff": "总裁办",
    "planning": "产品规划部",
    "review_control": "评审质控部",
    "delivery_ops": "交付运营部",
    "brand_content": "品牌内容部",
    "business_analysis": "经营分析部",
    "secops": "安全运维部",
    "compliance_test": "合规测试部",
    "engineering": "工程研发部",
    "people_ops": "人力组织部",
}


def extract_task_id(message: str) -> str | None:
    matches = sorted(set(NORMAL_TASK_ID_RE.findall(message or "")))
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(f"delegation message contains multiple task ids: {', '.join(matches)}")
    return matches[0]


def task_session_id(agent_id: str, task_id: str) -> str:
    return str(uuid.uuid5(SESSION_NAMESPACE, f"{agent_id}:{task_id}"))


def is_direct_task(message: str) -> bool:
    return any(marker in (message or "") for marker in DIRECT_TASK_MARKERS)


def get_agent_label(agent_id: str) -> str:
    return AGENT_LABELS.get(agent_id, agent_id)


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def run_kanban(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a kanban_update.py subcommand and return the result."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )


def kanban_create(task_id: str, title: str, agent_id: str, from_dept: str, to_dept: str) -> None:
    """Create a kanban entry for a delegated task and record the flow."""
    org = get_agent_label(agent_id)
    official = f"{org}负责人"

    # Step 1: Create the kanban card
    result = run_kanban([
        sys.executable,
        str(SCRIPT_DIR / "kanban_update.py"),
        "create",
        task_id,
        title,
        "Doing",
        org,
        official,
        f"总裁办直派{org}执行",
    ])
    if result.returncode != 0:
        print(f"[kanban] create failed: {result.stderr}", file=sys.stderr)
    else:
        print(f"[kanban] created {task_id}: {title}", file=sys.stderr)

    # Step 2: Record flow
    flow_result = run_kanban([
        sys.executable,
        str(SCRIPT_DIR / "kanban_update.py"),
        "flow",
        task_id,
        from_dept,
        to_dept,
        f"直派：{title}",
    ])
    if flow_result.returncode != 0:
        print(f"[kanban] flow failed: {flow_result.stderr}", file=sys.stderr)
    else:
        print(f"[kanban] flow {from_dept} → {to_dept}", file=sys.stderr)

    # Step 3: Report initial progress
    progress_result = run_kanban([
        sys.executable,
        str(SCRIPT_DIR / "kanban_update.py"),
        "progress",
        task_id,
        f"总裁办已直派{org}执行，等待结果回传",
        "消息分诊✅|整理需求✅|建单✅|直派执行🔄",
    ])
    if progress_result.returncode != 0:
        print(f"[kanban] progress failed: {progress_result.stderr}", file=sys.stderr)


def kanban_update_done(task_id: str, output: str, summary: str) -> None:
    """Mark a delegated task as done and archive the output."""
    done_result = run_kanban([
        sys.executable,
        str(SCRIPT_DIR / "kanban_update.py"),
        "done",
        task_id,
        output,
        summary,
    ])
    if done_result.returncode != 0:
        print(f"[kanban] done failed: {done_result.stderr}", file=sys.stderr)
    else:
        print(f"[kanban] marked done: {task_id}", file=sys.stderr)


def bind_main_session(agent_id: str, session_id: str) -> None:
    sessions_dir = AGENTS_ROOT / agent_id / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    sessions_file = sessions_dir / "sessions.json"
    try:
        payload = json.loads(sessions_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    key = f"agent:{agent_id}:main"
    row = payload.get(key, {})
    if not isinstance(row, dict):
        row = {}
    row["sessionId"] = session_id
    row["updatedAt"] = int(time.time() * 1000)
    payload[key] = row

    tmp = sessions_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(sessions_file)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Call another OpenClaw agent synchronously and print its reply.",
    )
    parser.add_argument("agent_id", help="Target OpenClaw agent id, e.g. planning")
    parser.add_argument("message", help="Message body to send to the target agent")
    parser.add_argument("--session-id", help="Explicit OpenClaw session id override")
    parser.add_argument("--timeout", type=int, default=1800, help="Agent timeout in seconds")
    parser.add_argument(
        "--kanban-id",
        help="Task ID for kanban tracking (e.g. L-20260401-001). "
             "When provided, automatically creates a kanban entry and records delegation flow.",
    )
    parser.add_argument(
        "--kanban-title",
        help="Task title for kanban entry. Required when --kanban-id is provided.",
    )
    parser.add_argument(
        "--kanban-update-done",
        metavar="SUMMARY",
        help="After delegation completes, mark the kanban task as done with this summary.",
    )
    args = parser.parse_args(argv[1:])

    # Determine if this is a direct task (no kanban tracking needed)
    is_direct = is_direct_task(args.message)

    # Handle kanban tracking for non-direct tasks
    if not is_direct and args.kanban_id and args.kanban_title:
        kanban_create(
            task_id=args.kanban_id,
            title=args.kanban_title,
            agent_id=args.agent_id,
            from_dept="总裁办",
            to_dept=get_agent_label(args.agent_id),
        )
    elif not is_direct and args.kanban_id:
        # kanban-id provided without title - just update state to Doing
        state_result = run_kanban([
            sys.executable,
            str(SCRIPT_DIR / "kanban_update.py"),
            "state",
            args.kanban_id,
            "Doing",
            f"总裁办已直派{get_agent_label(args.agent_id)}执行",
        ])
        if state_result.returncode != 0:
            print(f"[kanban] state update failed: {state_result.stderr}", file=sys.stderr)

    try:
        task_id = extract_task_id(args.message)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.session_id:
        session_id = args.session_id
    elif task_id:
        session_id = task_session_id(args.agent_id, task_id)
    elif is_direct:
        # Direct one-step delegation should also avoid reusing the target main session.
        session_id = str(uuid.uuid4())
    else:
        session_id = None

    if task_id and session_id:
        try:
            bind_main_session(args.agent_id, session_id)
        except Exception as exc:
            print(f"failed to prepare isolated session for {args.agent_id}/{task_id}: {exc}", file=sys.stderr)
            return 3

    cmd = [
        "openclaw",
        "--no-color",
        "agent",
        "--agent",
        args.agent_id,
    ]
    if session_id:
        cmd.extend(["--session-id", session_id])
    cmd.extend([
        "--message",
        args.message,
    ])
    cmd.extend(["--timeout", str(args.timeout)])

    proc = subprocess.run(cmd, capture_output=True, text=True)

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    if stdout:
        print(stdout)
    if proc.returncode != 0:
        if stderr:
            print(stderr, file=sys.stderr)
        return proc.returncode

    # If --kanban-update-done was provided, mark the task as done
    if args.kanban_update_done and args.kanban_id:
        # Try to extract output path from stdout if it looks like a file path
        output_text = stdout if stdout else ""
        kanban_update_done(args.kanban_id, output_text, args.kanban_update_done)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

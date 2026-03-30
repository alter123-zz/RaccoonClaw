#!/usr/bin/env python3
"""Delegate work to another OpenClaw agent via the local CLI.

For task-bearing messages, the delegate call is pinned to a deterministic
session id derived from ``agent_id + task id`` so different tasks do not
bleed into the same subagent conversation.
"""

from __future__ import annotations

import argparse
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
    args = parser.parse_args(argv[1:])

    try:
        task_id = extract_task_id(args.message)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.session_id:
        session_id = args.session_id
    elif task_id:
        session_id = task_session_id(args.agent_id, task_id)
    elif is_direct_task(args.message):
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

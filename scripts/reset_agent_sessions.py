#!/usr/bin/env python3
"""Backup and reset runtime agent sessions so updated prompts take effect immediately."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
import sys


OPENCLAW_HOME = pathlib.Path.home() / ".openclaw"
AGENTS_ROOT = OPENCLAW_HOME / "agents"
BACKUPS_ROOT = OPENCLAW_HOME / "backups"

DEFAULT_AGENTS = (
    "planning",
    "review_control",
    "delivery_ops",
    "engineering",
    "secops",
    "business_analysis",
    "brand_content",
    "compliance_test",
    "people_ops",
)


def _load_json(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: pathlib.Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _is_live_session(path: pathlib.Path) -> bool:
    name = path.name
    return (
        path.is_file()
        and name.endswith(".jsonl")
        and ".deleted." not in name
        and ".reset." not in name
    )


def reset_agent(agent_id: str, backup_dir: pathlib.Path, stamp: str) -> str:
    sessions_dir = AGENTS_ROOT / agent_id / "sessions"
    sessions_file = sessions_dir / "sessions.json"
    if not sessions_dir.exists():
        return f"{agent_id}: no sessions dir"

    agent_backup = backup_dir / agent_id
    agent_backup.mkdir(parents=True, exist_ok=True)
    if sessions_file.exists():
        shutil.copy2(sessions_file, agent_backup / "sessions.json")

    moved = 0
    for session_file in sorted(sessions_dir.iterdir()):
        if not _is_live_session(session_file):
            continue
        shutil.copy2(session_file, agent_backup / session_file.name)
        session_file.rename(session_file.with_name(f"{session_file.name}.reset.{stamp}"))
        moved += 1

    for lock_file in sessions_dir.glob("*.jsonl.lock"):
        shutil.copy2(lock_file, agent_backup / lock_file.name)
        lock_file.unlink(missing_ok=True)

    sessions = _load_json(sessions_file)
    session_count = len(sessions)
    _write_json(sessions_file, {})
    return f"{agent_id}: reset {moved} live session files, cleared {session_count} session records"


def main(argv: list[str]) -> int:
    agents = tuple(argv[1:]) or DEFAULT_AGENTS
    stamp = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_dir = BACKUPS_ROOT / f"agent-session-reset-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"backup: {backup_dir}")
    for agent_id in agents:
        print(reset_agent(agent_id, backup_dir, stamp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

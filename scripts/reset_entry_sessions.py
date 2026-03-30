#!/usr/bin/env python3
"""Backup entry prompts, refresh runtime SOUL files, and reset chief_of_staff sessions."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
import sys


OPENCLAW_HOME = pathlib.Path.home() / ".openclaw"
AGENTS_ROOT = OPENCLAW_HOME / "agents"
BACKUPS_ROOT = OPENCLAW_HOME / "backups"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
ENTRY_SOUL = PROJECT_ROOT / "agents" / "chief_of_staff" / "SOUL.md"
TARGETS = (
    ("chief_of_staff", "agent:chief_of_staff:main"),
)
PROMPT_TARGETS = (
    ("workspace-chief_of_staff", OPENCLAW_HOME / "workspace-chief_of_staff" / "SOUL.md"),
    ("agent-chief_of_staff", OPENCLAW_HOME / "agents" / "chief_of_staff" / "SOUL.md"),
)


def _load_json(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _write_json(path: pathlib.Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sync_entry_prompts(backup_dir: pathlib.Path) -> list[str]:
    src_text = ENTRY_SOUL.read_text(encoding="utf-8")
    prompt_backup = backup_dir / "prompts"
    prompt_backup.mkdir(parents=True, exist_ok=True)

    results = []
    for label, dst in PROMPT_TARGETS:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.copy2(dst, prompt_backup / f"{label}-SOUL.md")
            current = dst.read_text(encoding="utf-8", errors="ignore")
        else:
            current = ""
        if current == src_text:
            results.append(f"{label}: prompt already current")
            continue
        dst.write_text(src_text, encoding="utf-8")
        results.append(f"{label}: prompt refreshed")
    return results


def reset_target(agent_id: str, session_key: str, backup_dir: pathlib.Path, stamp: str) -> str:
    sessions_dir = AGENTS_ROOT / agent_id / "sessions"
    sessions_file = sessions_dir / "sessions.json"
    sessions = _load_json(sessions_file)
    record = sessions.get(session_key)
    if not record:
        return f"{agent_id}: no active entry session"

    session_id = record.get("sessionId", "").strip()
    session_file = sessions_dir / f"{session_id}.jsonl" if session_id else None

    agent_backup = backup_dir / agent_id
    agent_backup.mkdir(parents=True, exist_ok=True)
    if sessions_file.exists():
        shutil.copy2(sessions_file, agent_backup / "sessions.json")

    session_note = "session file missing"
    if session_file and session_file.exists():
        renamed = session_file.with_name(f"{session_file.name}.reset.{stamp}")
        shutil.copy2(session_file, agent_backup / session_file.name)
        session_file.rename(renamed)
        session_note = f"reset {session_file.name}"

    sessions.pop(session_key, None)
    _write_json(sessions_file, sessions)
    return f"{agent_id}: removed {session_key} ({session_note})"


def main() -> int:
    stamp = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    backup_dir = BACKUPS_ROOT / f"entry-session-reset-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    results = []
    results.extend(sync_entry_prompts(backup_dir))
    results.extend(reset_target(agent_id, session_key, backup_dir, stamp) for agent_id, session_key in TARGETS)

    print(f"backup: {backup_dir}")
    for line in results:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

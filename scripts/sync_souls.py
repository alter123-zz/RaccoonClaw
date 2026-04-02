#!/usr/bin/env python3
"""
Sync agent SOUL.md and scripts from project to OpenClaw workspaces.

Usage:
    python3 scripts/sync_souls.py                     # sync all
    python3 scripts/sync_souls.py chief_of_staff       # sync one

After syncing, run:  openclaw gateway restart
"""

from __future__ import annotations

import pathlib
import shutil
import sys

BASE = pathlib.Path(__file__).parent.parent
AGENTS_DIR = BASE / "agents"
OPENCLAW_HOME = pathlib.Path.home() / ".openclaw"

AGENT_NAMES = sorted(p.name for p in AGENTS_DIR.iterdir() if p.is_dir())

# Scripts to sync into each agent workspace (if they exist in project)
_SCRIPTS_TO_SYNC = [
    "chief_of_staff_council.py",
    "delegate_agent.py",
    "intake_guard.py",
    "kanban_update.py",
    "extract_task_context.py",
    "blocker_feedback.py",
    "task_ids.py",
    "runtime_paths.py",
    "utils.py",
    "file_lock.py",
    "browser_cli.py",
]


def sync_soul(agent_name: str) -> bool:
    src = AGENTS_DIR / agent_name / "SOUL.md"
    if not src.exists():
        print(f"  SKIP: {agent_name} (no SOUL.md)")
        return False

    workspace = OPENCLAW_HOME / f"workspace-{agent_name}"
    if not workspace.is_dir():
        print(f"  SKIP: {agent_name} (no workspace)")
        return False

    changed = False

    # Sync SOUL.md
    dst = workspace / "SOUL.md"
    if dst.exists() and dst.read_text() == src.read_text():
        pass
    else:
        shutil.copy2(src, dst)
        print(f"  SYNC: {agent_name}/SOUL.md")
        changed = True

    # Sync scripts
    scripts_dir = workspace / "scripts"
    if scripts_dir.is_dir():
        for script_name in _SCRIPTS_TO_SYNC:
            src_script = BASE / "scripts" / script_name
            if not src_script.exists():
                continue
            dst_script = scripts_dir / script_name
            if not dst_script.exists() or dst_script.read_text() != src_script.read_text():
                shutil.copy2(src_script, dst_script)
                print(f"  SYNC: {agent_name}/scripts/{script_name}")
                changed = True

    if not changed:
        print(f"  OK:   {agent_name}")

    return changed


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else AGENT_NAMES
    changed = 0
    for name in targets:
        if name not in AGENT_NAMES:
            print(f"  WARN: unknown agent '{name}'")
            continue
        if sync_soul(name):
            changed += 1

    if changed:
        print(f"\nSynced {changed} item(s). Run: openclaw gateway restart")
    else:
        print("\nAll in sync.")


if __name__ == "__main__":
    main()

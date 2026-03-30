#!/usr/bin/env python3
"""Shared workflow configuration loader for the workbench project."""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


def _resolve_shared_root() -> Path:
    project_root = os.environ.get("OPENCLAW_PROJECT_ROOT", "").strip()
    if project_root:
        return Path(project_root).expanduser() / "shared"
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "shared"
    return Path(__file__).resolve().parent.parent / "shared"


WORKFLOW_PATH = _resolve_shared_root() / "workflow-config.json"


@lru_cache(maxsize=1)
def load_workflow_config() -> dict[str, Any]:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def workflow_pipeline() -> list[dict[str, str]]:
    return list(load_workflow_config()["pipeline"])


def workflow_state_index() -> dict[str, int]:
    return dict(load_workflow_config()["stateIndex"])


def workflow_state_labels() -> dict[str, str]:
    return dict(load_workflow_config()["stateLabels"])


def workflow_board_order() -> dict[str, int]:
    return dict(load_workflow_config()["boardOrder"])


def workflow_terminal_states() -> set[str]:
    return set(load_workflow_config()["terminalStates"])


def workflow_state_agent_map() -> dict[str, str | None]:
    return dict(load_workflow_config()["stateAgentMap"])


def workflow_org_resolved_states() -> set[str]:
    return set(load_workflow_config()["orgResolvedStates"])


def workflow_manual_advance() -> dict[str, tuple[str, str, str, str]]:
    manual_advance = load_workflow_config()["manualAdvance"]
    return {
        state: (
            step["next"],
            step["from"],
            step["to"],
            step["remark"],
        )
        for state, step in manual_advance.items()
    }

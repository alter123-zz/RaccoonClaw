#!/usr/bin/env python3
"""Resolve canonical runtime/workbench data paths."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
REPO_DATA_DIR = BASE / "data"
_ENV_PREFIX = "OPENCLAW_"
DEFAULT_WORKSPACE_ID = os.environ.get("OPENCLAW_WORKSPACE", "chief_of_staff").strip() or "chief_of_staff"
PREFERRED_WORKSPACE_IDS = ("chief_of_staff",)
DATA_PRIORITY_FILES = ("agent_config.json", "officials_stats.json", "live_status.json", "tasks_source.json")


def _env_path(key: str) -> Path | None:
    value = os.environ.get(key, "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def openclaw_home() -> Path:
    return _env_path(f"{_ENV_PREFIX}HOME") or (Path.home() / ".openclaw")


def openclaw_config_path() -> Path:
    return _env_path(f"{_ENV_PREFIX}CONFIG_PATH") or (openclaw_home() / "openclaw.json")


def _workspace_env_key(agent_id: str) -> str:
    normalized = str(agent_id or "").strip().upper().replace("-", "_")
    return f"{_ENV_PREFIX}WORKSPACE_{normalized}"


def repo_data_dir() -> Path:
    REPO_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return REPO_DATA_DIR


@lru_cache(maxsize=1)
def _load_openclaw_cfg() -> dict:
    try:
        return json.loads(openclaw_config_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def _agent_workspace(agent_id: str) -> Path | None:
    env_override = _env_path(_workspace_env_key(agent_id))
    if env_override:
        return env_override
    cfg = _load_openclaw_cfg()
    for agent in cfg.get("agents", {}).get("list", []):
        if agent.get("id") == agent_id and agent.get("workspace"):
            return Path(agent["workspace"]).expanduser()
    return None


def configured_agent_workspaces() -> dict[str, Path]:
    cfg = _load_openclaw_cfg()
    result: dict[str, Path] = {}
    for agent in cfg.get("agents", {}).get("list", []):
        agent_id = str(agent.get("id") or "").strip()
        workspace = str(agent.get("workspace") or "").strip()
        if agent_id and workspace:
            result[agent_id] = Path(workspace).expanduser()
    return result


def discovered_workspace_dirs() -> list[Path]:
    cfg = _load_openclaw_cfg()
    candidates: list[Path] = []

    env_primary = _env_path(f"{_ENV_PREFIX}PRIMARY_WORKSPACE")
    if env_primary:
        candidates.append(env_primary)

    env_workspaces = os.environ.get(f"{_ENV_PREFIX}WORKSPACES", "").strip()
    if env_workspaces:
        for raw in env_workspaces.split(os.pathsep):
            raw = raw.strip()
            if raw:
                candidates.append(Path(raw).expanduser())

    for ws in configured_agent_workspaces().values():
        candidates.append(ws)

    default_ws = cfg.get("agents", {}).get("defaults", {}).get("workspace")
    if isinstance(default_ws, str) and default_ws.strip():
        candidates.append(Path(default_ws).expanduser())

    home = openclaw_home()
    if home.exists():
        candidates.extend(sorted(home.glob("workspace-*")))

    seen: set[str] = set()
    discovered: list[Path] = []
    for ws in candidates:
        key = str(ws.resolve()) if ws.exists() else str(ws)
        if key in seen:
            continue
        seen.add(key)
        if (ws / "data").is_dir() or ws.is_dir():
            discovered.append(ws)
    return discovered


def workspace_dir_for(agent_id: str, include_legacy: bool = True) -> Path | None:
    candidates: list[Path] = []
    workspace = _agent_workspace(agent_id)
    if workspace:
        candidates.append(workspace)

    fallback = openclaw_home() / f"workspace-{agent_id}"
    candidates.append(fallback)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else None


def canonical_workspace_dir() -> Path:
    preferred_env_ws = openclaw_home() / f"workspace-{DEFAULT_WORKSPACE_ID}"
    candidates: list[Path] = []

    for agent_id in PREFERRED_WORKSPACE_IDS:
        ws = workspace_dir_for(agent_id)
        if ws:
            candidates.append(ws)

    candidates.extend([
        openclaw_home() / "workspace-chief_of_staff",
        preferred_env_ws,
    ])
    candidates.extend(discovered_workspace_dirs())

    seen: set[str] = set()
    scored: list[tuple[int, Path]] = []
    for ws in candidates:
        key = str(ws.resolve()) if ws.exists() else str(ws)
        if key in seen:
            continue
        seen.add(key)
        if not ws.exists():
            continue
        score = 0
        data_dir = ws / "data"
        if data_dir.is_dir():
            score += 10
        for name in DATA_PRIORITY_FILES:
            if (data_dir / name).exists():
                score += 25
        if (ws / "deliverables").is_dir():
            score += 5
        scored.append((score, ws))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        top_score, top_ws = scored[0]
        if top_score > 0 or top_ws.is_dir():
            return top_ws

    if "OPENCLAW_HOME" in os.environ:
        return preferred_env_ws

    discovered = discovered_workspace_dirs()
    if discovered:
        return discovered[0]

    return BASE


def canonical_data_dir() -> Path:
    ws = canonical_workspace_dir()
    if ws == BASE:
        return repo_data_dir()
    data_dir = ws / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def legacy_deliverables_root() -> Path:
    ws = canonical_workspace_dir()
    if ws == BASE:
        root = repo_data_dir() / "deliverables"
    else:
        root = ws / "deliverables"
    root.mkdir(parents=True, exist_ok=True)
    return root


def canonical_deliverables_root() -> Path:
    root = canonical_data_dir() / "deliverables"
    root.mkdir(parents=True, exist_ok=True)
    return root


def candidate_deliverables_roots() -> list[Path]:
    roots = [canonical_deliverables_root()]
    legacy_root = legacy_deliverables_root()
    if legacy_root not in roots:
        roots.append(legacy_root)
    return roots


def canonical_task_deliverables_dir(task_id: str) -> Path:
    task_dir = canonical_deliverables_root() / str(task_id or "misc").strip()
    task_dir.mkdir(parents=True, exist_ok=True)
    return task_dir


def read_preferred_json(name: str, default):
    for base in (canonical_data_dir(), repo_data_dir()):
        path = base / name
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return default


def openclaw_agents_root() -> Path:
    return _env_path(f"{_ENV_PREFIX}AGENTS_ROOT") or (openclaw_home() / "agents")


def agent_dir(agent_id: str) -> Path:
    return openclaw_agents_root() / str(agent_id)


def agent_sessions_dir(agent_id: str) -> Path:
    return agent_dir(agent_id) / "sessions"

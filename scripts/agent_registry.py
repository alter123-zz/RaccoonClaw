#!/usr/bin/env python3
"""Shared agent registry loader for RaccoonClaw-OSS."""

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
    return Path(__file__).resolve().parent.parent / "shared"


REGISTRY_PATH = _resolve_shared_root() / "agent-registry.json"

CANONICAL_RUNTIME_PREFERENCE = {
    "chief_of_staff": ("chief_of_staff",),
    "planning": ("planning",),
    "review_control": ("review_control",),
    "delivery_ops": ("delivery_ops",),
    "business_analysis": ("business_analysis",),
    "brand_content": ("brand_content",),
    "secops": ("secops",),
    "compliance_test": ("compliance_test",),
    "engineering": ("engineering",),
    "people_ops": ("people_ops",),
}


def canonical_agent_id(agent_id: str) -> str:
    return agent_id


def runtime_candidate_ids(agent_id: str) -> list[str]:
    canonical = canonical_agent_id(agent_id)
    candidates = list(CANONICAL_RUNTIME_PREFERENCE.get(canonical, (canonical,)))
    if agent_id not in candidates:
        candidates.insert(0, agent_id)
    deduped: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _openclaw_home() -> Path:
    return Path(os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw"))).expanduser()


def runtime_configured_agent_ids() -> list[str]:
    home = _openclaw_home()
    cfg_path = home / "openclaw.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    known: list[str] = []
    for item in (cfg.get("agents", {}) or {}).get("list", []) or []:
        if not isinstance(item, dict):
            continue
        agent_id = str(item.get("id") or "").strip()
        if agent_id and agent_id not in known:
            known.append(agent_id)
    return known


def runtime_known_agent_ids() -> list[str]:
    home = _openclaw_home()
    known: list[str] = []
    for agent_id in runtime_configured_agent_ids():
        if agent_id and agent_id not in known:
            known.append(agent_id)
    agents_root = home / "agents"
    if agents_root.exists():
        for path in sorted(agents_root.iterdir()):
            if path.is_dir() and path.name not in known:
                known.append(path.name)
    return known


def resolve_runtime_agent_id(agent_id: str) -> str:
    configured = runtime_configured_agent_ids()
    if configured:
        configured_set = set(configured)
        for candidate in runtime_candidate_ids(agent_id):
            if candidate in configured_set:
                return candidate
    available = set(runtime_known_agent_ids())
    for candidate in runtime_candidate_ids(agent_id):
        if candidate in available:
            return candidate
    return canonical_agent_id(agent_id)


@lru_cache(maxsize=1)
def load_agent_registry() -> list[dict[str, Any]]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def agent_registry_by_id() -> dict[str, dict[str, Any]]:
    return {agent["id"]: agent for agent in load_agent_registry()}


def sync_agent_labels() -> dict[str, dict[str, str]]:
    return {
        agent["id"]: {
            "label": agent["label"],
            "role": agent["displayRole"],
            "duty": agent["duty"],
            "emoji": agent["emoji"],
        }
        for agent in load_agent_registry()
    }


def dashboard_agent_depts() -> list[dict[str, str]]:
    return [
        {
            "id": resolve_runtime_agent_id(agent["id"]),
            "label": agent["label"],
            "emoji": agent["emoji"],
            "role": agent["displayRole"],
            "rank": agent["rank"],
        }
        for agent in load_agent_registry()
    ]


def officials_registry() -> list[dict[str, str]]:
    return [
        {
            "id": agent["id"],
            "label": agent["label"],
            "emoji": agent["emoji"],
            "role": agent["displayRole"],
            "rank": agent["rank"],
        }
        for agent in load_agent_registry()
    ]


def org_agent_map() -> dict[str, str]:
    return {agent["label"]: agent["id"] for agent in load_agent_registry()}


def backend_agent_meta() -> dict[str, dict[str, str]]:
    return {
        agent["id"]: {
            "name": agent["label"],
            "role": agent["apiRole"],
            "icon": agent["emoji"],
        }
        for agent in load_agent_registry()
    }

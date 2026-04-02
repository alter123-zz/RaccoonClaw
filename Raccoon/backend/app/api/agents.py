"""Agents API — 现代公司架构下的 Agent 配置和状态查询。"""

import json
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

log = logging.getLogger("edict.api.agents")
router = APIRouter()


def _project_root() -> Path:
    project_root = os.environ.get("OPENCLAW_PROJECT_ROOT", "").strip()
    if project_root:
        return Path(project_root).expanduser()
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return Path(__file__).parents[4]


ROOT = _project_root()
REGISTRY_PATH = ROOT / "shared" / "agent-registry.json"


@lru_cache(maxsize=1)
def _load_agent_meta() -> dict[str, dict[str, str]]:
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("failed to load agent registry: %s", exc)
        return {}
    return {
        agent["id"]: {
            "name": agent["label"],
            "role": agent["apiRole"],
            "icon": agent["emoji"],
        }
        for agent in registry
    }


AGENT_META = _load_agent_meta()


@router.get("")
async def list_agents():
    """列出所有可用 Agent。"""
    agents = []
    for agent_id, meta in AGENT_META.items():
        agents.append({
            "id": agent_id,
            **meta,
        })
    return {"agents": agents}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """获取 Agent 详情。"""
    meta = AGENT_META.get(agent_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # 尝试读取 SOUL.md
    soul_path = ROOT / "agents" / agent_id / "SOUL.md"
    soul_content = ""
    if soul_path.exists():
        soul_content = soul_path.read_text(encoding="utf-8")[:2000]

    return {
        "id": agent_id,
        **meta,
        "soul_preview": soul_content,
    }


@router.get("/{agent_id}/config")
async def get_agent_config(agent_id: str):
    """获取 Agent 运行时配置。"""
    config_path = ROOT / "data" / "agent_config.json"
    if not config_path.exists():
        return {"agent_id": agent_id, "config": {}}

    try:
        configs = json.loads(config_path.read_text(encoding="utf-8"))
        agent_config = configs.get(agent_id, {})
        return {"agent_id": agent_id, "config": agent_config}
    except (json.JSONDecodeError, IOError):
        return {"agent_id": agent_id, "config": {}}

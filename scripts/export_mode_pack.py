#!/usr/bin/env python3
"""Export a reusable workbench mode pack with prompts and governance config."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from agent_registry import agent_registry_by_id
from review_rubric import resolve_profile
from utils import beijing_now
from workbench_modes import load_workbench_modes


ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents"
SHARED_DIR = ROOT / "shared"
EXPORT_ROOT = ROOT / "exports" / "mode-packs"


def _mode_map() -> dict[str, dict[str, Any]]:
    return {str(mode["key"]): mode for mode in load_workbench_modes()}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def export_mode_pack(mode_key: str, out_root: Path) -> Path:
    modes = _mode_map()
    if mode_key not in modes:
        raise SystemExit(f"未知模式: {mode_key}")

    mode = modes[mode_key]
    registry = agent_registry_by_id()
    pack_dir = out_root / mode_key
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    (pack_dir / "agents").mkdir(parents=True, exist_ok=True)
    (pack_dir / "configs").mkdir(parents=True, exist_ok=True)

    agents_payload = []
    for agent_id in mode.get("agentIds", []):
        meta = registry.get(agent_id)
        if not meta:
            continue
        src = AGENTS_DIR / agent_id / "SOUL.md"
        dst = pack_dir / "agents" / agent_id / "SOUL.md"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.copy2(src, dst)
        agents_payload.append(meta)

    rubric = resolve_profile(mode_key, "")
    incident_playbook = json.loads((SHARED_DIR / "incident-playbook.json").read_text(encoding="utf-8"))
    manifest = {
        "generatedAt": beijing_now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "agents": agents_payload,
        "reviewRubric": {
            "profileKey": rubric["key"],
            "profileLabel": rubric["label"],
            "requiredChecks": rubric["requiredChecks"],
            "readinessChecks": rubric["readinessChecks"],
            "focus": rubric["focus"],
        },
        "incidentPlaybook": incident_playbook,
    }
    _write_json(pack_dir / "manifest.json", manifest)
    _write_json(pack_dir / "configs" / "workbench-mode.json", mode)
    _write_json(pack_dir / "configs" / "review-rubric.json", rubric)
    shutil.copy2(SHARED_DIR / "incident-playbook.json", pack_dir / "configs" / "incident-playbook.json")

    readme_lines = [
        f"# {mode['label']} 模式包",
        "",
        f"- 模式标识：`{mode_key}`",
        f"- 说明：{mode['desc']}",
        f"- 默认目标部门：{mode['defaultTargetDept']}",
        f"- 模板 ID：{', '.join(mode.get('templateIds', [])) or '无'}",
        f"- 工作流：{' -> '.join(mode.get('workflow', []))}",
        "",
        "## 包含内容",
        "- agents/: 当前模式涉及的 Agent prompt",
        "- configs/workbench-mode.json: 模式定义",
        "- configs/review-rubric.json: 当前模式评审标准",
        "- configs/incident-playbook.json: 自动化故障分级与 runbook",
        "- manifest.json: 安装和同步所需元数据"
    ]
    (pack_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    return pack_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a reusable workbench mode pack")
    parser.add_argument("--mode", required=True, help="Workbench mode id, e.g. content_creation")
    parser.add_argument("--out", default=str(EXPORT_ROOT), help="Output directory")
    args = parser.parse_args()

    pack_dir = export_mode_pack(args.mode, Path(args.out).expanduser())
    print(str(pack_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Seed clean or demo runtime data for community onboarding."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CANONICAL_AGENTS = (
    "chief_of_staff",
    "planning",
    "review_control",
    "delivery_ops",
    "brand_content",
    "business_analysis",
    "secops",
    "compliance_test",
    "engineering",
    "people_ops",
)

BASE_FILES = {
    "agent_config.json": {"agents": []},
    "live_status.json": {},
    "model_change_log.json": [],
    "officials_stats.json": {"officials": []},
    "pending_model_changes.json": [],
    "sync_status.json": {},
    "tasks.json": [],
    "tasks_source.json": [],
}


def _write_json(path: Path, payload, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_openclaw_config(openclaw_home: Path, force: bool) -> None:
    config_path = openclaw_home / "openclaw.json"
    if config_path.exists() and not force:
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "tools": {"profile": "coding"},
        "commands": {"ownerDisplay": "hash"},
        "agents": {
            "list": [
                {
                    "id": agent_id,
                    "workspace": str(openclaw_home / f"workspace-{agent_id}"),
                    "subagents": {"allowAgents": []},
                }
                for agent_id in CANONICAL_AGENTS
            ]
        },
    }
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _ensure_workspaces(openclaw_home: Path) -> None:
    (openclaw_home / "agents").mkdir(parents=True, exist_ok=True)
    for agent_id in CANONICAL_AGENTS:
        workspace = openclaw_home / f"workspace-{agent_id}"
        (workspace / "data").mkdir(parents=True, exist_ok=True)
        (workspace / "skills").mkdir(parents=True, exist_ok=True)


def _seed_base_data(repo_data_dir: Path, runtime_data_dir: Path, force: bool) -> None:
    for name, payload in BASE_FILES.items():
        _write_json(repo_data_dir / name, payload, force)
        _write_json(runtime_data_dir / name, payload, force)


def _demo_payload(runtime_data_dir: Path) -> tuple[list[dict], dict]:
    deliverable_dir = runtime_data_dir / "deliverables" / "L-20260101-001"
    deliverable_dir.mkdir(parents=True, exist_ok=True)
    deliverable_path = deliverable_dir / "L-20260101-001_demo-summary.md"
    deliverable_path.write_text(
        "# Demo Deliverable\n\nThis is a seeded demo task for the community edition.\n",
        encoding="utf-8",
    )

    tasks = [
        {
            "id": "L-20260101-001",
            "title": "Demo 任务：欢迎查看交付归档",
            "official": "总裁办",
            "state": "Done",
            "org": "品牌内容部",
            "now": "已完成：演示交付已归档",
            "eta": "-",
            "block": "无",
            "ac": "查看交付归档与搜索能力",
            "output": str(deliverable_path),
            "resolvedOutput": str(deliverable_path),
            "heartbeat": {"status": "active", "label": "✅"},
            "flow_log": [
                {"at": "2026-01-01T09:00:00+08:00", "from": "总裁办", "to": "品牌内容部", "remark": "light 直派"},
                {"at": "2026-01-01T09:18:00+08:00", "from": "品牌内容部", "to": "交付归档", "remark": "已完成"},
            ],
            "todos": [{"id": "return", "title": "回传总裁办", "status": "completed"}],
            "review_round": 0,
            "archived": False,
            "updatedAt": "2026-01-01T09:18:00+08:00",
            "sourceMeta": {"flowMode": "light", "taskKind": "oneshot"},
        },
        {
            "id": "L-20260101-002",
            "title": "Demo 定时任务：每日摘要",
            "official": "总裁办",
            "state": "Assigned",
            "org": "调度器",
            "now": "等待调度执行：定时任务 · 每日 09:00",
            "eta": "2026-01-02 09:00",
            "block": "无",
            "ac": "按计划自动投递",
            "output": "定时任务 · 每日 09:00",
            "heartbeat": {"status": "active", "label": "⏰"},
            "flow_log": [
                {"at": "2026-01-01T08:58:00+08:00", "from": "调度器", "to": "总裁办", "remark": "已登记为每日任务"}
            ],
            "todos": [],
            "review_round": 0,
            "archived": False,
            "updatedAt": "2026-01-01T08:58:00+08:00",
            "sourceMeta": {
                "flowMode": "light",
                "taskKind": "recurring",
                "scheduleMode": "daily",
                "scheduleTime": "09:00",
                "scheduleLabel": "每日 09:00",
                "nextRunAt": "2026-01-02T01:00:00Z",
                "lastRunStatus": "pending",
                "lastDeliveryStatus": "pending",
                "automationJobId": "task-L-20260101-002",
                "target": "L-20260101-002",
                "enabled": True,
                "jobEnabled": True,
            },
        },
    ]
    jobs = {
        "jobs": [
            {
                "id": "task-L-20260101-002",
                "name": "Demo 定时任务：每日摘要",
                "taskId": "L-20260101-002",
                "agentId": "chief_of_staff",
                "enabled": True,
                "schedule": {
                    "kind": "recurring",
                    "mode": "daily",
                    "time": "09:00",
                    "label": "每日 09:00",
                    "tz": "Asia/Shanghai",
                },
                "payload": {
                    "taskId": "L-20260101-002",
                    "title": "Demo 定时任务：每日摘要",
                    "message": "Seeded demo recurring task",
                    "flowMode": "light",
                },
                "delivery": {"channel": "workbench", "to": "L-20260101-002"},
                "state": {
                    "consecutiveErrors": 0,
                    "lastRunAtMs": None,
                    "nextRunAtMs": 1767315600000,
                    "lastRunStatus": "pending",
                    "lastDeliveryStatus": "pending",
                    "running": False,
                },
            }
        ]
    }
    return tasks, jobs


def seed_profile(openclaw_home: Path, repo_data_dir: Path, profile: str, force: bool) -> None:
    runtime_data_dir = openclaw_home / "workspace-chief_of_staff" / "data"
    cron_dir = openclaw_home / "cron"

    _ensure_openclaw_config(openclaw_home, force)
    _ensure_workspaces(openclaw_home)
    _seed_base_data(repo_data_dir, runtime_data_dir, force)

    if profile == "demo":
        tasks, jobs = _demo_payload(runtime_data_dir)
        _write_json(runtime_data_dir / "tasks_source.json", tasks, True if force else False)
        _write_json(repo_data_dir / "tasks_source.json", tasks, True if force else False)
        _write_json(cron_dir / "jobs.json", jobs, force)
    else:
        _write_json(cron_dir / "jobs.json", {"jobs": []}, force)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed clean or demo runtime data.")
    parser.add_argument("--profile", choices=("clean", "demo"), default="clean")
    parser.add_argument("--openclaw-home", type=Path, default=None)
    parser.add_argument("--repo-dir", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_dir = args.repo_dir.resolve()
    openclaw_home = (args.openclaw_home or (repo_dir / ".openclaw")).expanduser().resolve()
    repo_data_dir = repo_dir / "data"
    seed_profile(openclaw_home, repo_data_dir, args.profile, args.force)
    print(
        json.dumps(
            {
                "ok": True,
                "profile": args.profile,
                "openclawHome": str(openclaw_home),
                "repoDataDir": str(repo_data_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

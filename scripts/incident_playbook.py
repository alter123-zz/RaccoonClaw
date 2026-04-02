#!/usr/bin/env python3
"""Shared incident severity and runbook helpers for automation monitoring."""

from __future__ import annotations

import datetime as _dt
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK_PATH = ROOT / "shared" / "incident-playbook.json"

_DELIVERY_ERROR_STATUSES = {"error", "failed", "undelivered"}
_EXECUTION_ERROR_STATUSES = {"error", "failed", "timeout"}


@lru_cache(maxsize=1)
def load_incident_playbook() -> dict[str, Any]:
    return json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))


def _severity_map() -> dict[str, dict[str, Any]]:
    config = load_incident_playbook()
    return {
        str(item["key"]): item
        for item in config.get("severityLevels", [])
        if isinstance(item, dict) and item.get("key")
    }


def _playbook(kind: str) -> dict[str, Any]:
    config = load_incident_playbook()
    playbooks = config.get("playbooks", {})
    candidate = playbooks.get(kind, {})
    return candidate if isinstance(candidate, dict) else {}


def _next_update(now_ms: int, severity_key: str) -> str | None:
    level = _severity_map().get(severity_key)
    if not level:
        return None
    minutes = int(level.get("updateWithinMin") or 0)
    if minutes <= 0:
        return None
    dt = _dt.datetime.fromtimestamp(now_ms / 1000, tz=_dt.timezone.utc) + _dt.timedelta(minutes=minutes)
    return dt.isoformat().replace("+00:00", "Z")


def classify_incident(job: dict[str, Any], now_ms: int) -> dict[str, Any] | None:
    status = str(job.get("status") or "")
    if status not in {"warning", "critical"}:
        return None

    last_delivery = str(job.get("lastDeliveryStatus") or "").lower()
    last_run = str(job.get("lastRunStatus") or "").lower()
    consecutive_errors = int(job.get("consecutiveErrors") or 0)
    interval_ms = job.get("intervalMs")
    channel = str(job.get("channel") or "")
    target = str(job.get("target") or "")
    overdue_ms = int(job.get("overdueMs") or 0)

    if last_delivery in _DELIVERY_ERROR_STATUSES:
        kind = "delivery_failed"
    elif last_run in _EXECUTION_ERROR_STATUSES or consecutive_errors > 0:
        kind = "execution_failed"
    elif status == "warning" and not job.get("lastRunAt"):
        kind = "first_run_timeout"
    else:
        kind = "overdue"

    playbook = _playbook(kind)
    severity_key = str(playbook.get("defaultSeverity") or "sev4")

    if kind == "delivery_failed" and not target:
        severity_key = "sev2"
    elif kind == "execution_failed" and consecutive_errors >= 2:
        severity_key = "sev2"
    elif kind == "overdue":
        if isinstance(interval_ms, (int, float)) and interval_ms <= 30 * 60 * 1000:
            severity_key = "sev2" if overdue_ms >= 30 * 60 * 1000 else "sev3"
        else:
            severity_key = "sev4"
    elif kind == "first_run_timeout":
        severity_key = "sev4"

    level = _severity_map().get(severity_key, {})
    summary = str(playbook.get("summary") or "")
    if kind == "delivery_failed" and channel and target:
        summary = f"{summary} 当前目标：{channel} -> {target}"
    elif kind == "execution_failed" and job.get("lastError"):
        summary = str(job.get("lastError"))[:120]
    elif kind == "overdue" and job.get("nextRunAt"):
        summary = f"超过计划执行时间仍无新记录，原计划时间 {job['nextRunAt']}"

    return {
        "kind": kind,
        "label": str(playbook.get("label") or "自动化异常"),
        "severity": severity_key,
        "severityLabel": str(level.get("label") or severity_key.upper()),
        "tone": str(level.get("tone") or "warn"),
        "summary": summary or str(level.get("summary") or ""),
        "ownerDept": str(playbook.get("ownerDept") or "总裁办"),
        "steps": [str(step) for step in playbook.get("steps", []) if str(step).strip()],
        "nextUpdateBy": _next_update(now_ms, severity_key),
        "updateWithinMin": int(level.get("updateWithinMin") or 0),
    }


def build_incident_summary(jobs: list[dict[str, Any]], now_ms: int) -> dict[str, Any] | None:
    incidents = [job.get("incident") for job in jobs if isinstance(job.get("incident"), dict)]
    if not incidents:
        return None

    rank = {"sev1": 0, "sev2": 1, "sev3": 2, "sev4": 3}
    incidents.sort(key=lambda item: (rank.get(str(item.get("severity")), 9), str(item.get("ownerDept") or "")))
    lead = incidents[0]
    affected = [
        {
          "jobId": str(job.get("id") or ""),
          "jobName": str(job.get("name") or "未命名任务"),
          "severity": job["incident"]["severity"],
          "severityLabel": job["incident"]["severityLabel"],
        }
        for job in jobs
        if isinstance(job.get("incident"), dict)
    ]
    return {
        "severity": lead["severity"],
        "severityLabel": lead["severityLabel"],
        "tone": lead["tone"],
        "title": lead["label"],
        "summary": lead["summary"],
        "ownerDept": lead["ownerDept"],
        "steps": lead["steps"],
        "nextUpdateBy": lead["nextUpdateBy"],
        "affectedJobs": affected,
        "count": len(affected),
    }

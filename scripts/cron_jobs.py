#!/usr/bin/env python3
"""Minimal cron job registry for workbench scheduled tasks."""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any

from file_lock import atomic_json_read, atomic_json_update
from runtime_paths import openclaw_home


SH_TZ = dt.timezone(dt.timedelta(hours=8))
CRON_ROOT = openclaw_home() / "cron"
CRON_JOBS_PATH = CRON_ROOT / "jobs.json"
CRON_RUNS_DIR = CRON_ROOT / "runs"


def ensure_cron_dirs() -> None:
    CRON_ROOT.mkdir(parents=True, exist_ok=True)
    CRON_RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _now_ms() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)


def _task_created_ms(task: dict[str, Any]) -> int | None:
    flow_log = task.get("flow_log") or []
    if isinstance(flow_log, list):
        for entry in flow_log:
            if not isinstance(entry, dict):
                continue
            raw = entry.get("at")
            value = _parse_any_time_ms(raw)
            if value:
                return value
    return _parse_any_time_ms(task.get("updatedAt"))


def _parse_any_time_ms(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    try:
        if isinstance(raw, (int, float)):
            value = int(raw)
            return value if value > 10_000_000_000 else value * 1000
        text = str(raw).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return int(dt.datetime.fromisoformat(text).timestamp() * 1000)
    except Exception:
        return None


def _format_iso(ms: int | None) -> str | None:
    if not isinstance(ms, int) or ms <= 0:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time_hm(value: str) -> tuple[int, int]:
    raw = str(value or "").strip() or "09:00"
    hour_str, _, minute_str = raw.partition(":")
    try:
        hour = min(23, max(0, int(hour_str)))
    except Exception:
        hour = 9
    try:
        minute = min(59, max(0, int(minute_str or "0")))
    except Exception:
        minute = 0
    return hour, minute


def _cron_expr_for_task(task_kind: str, schedule_mode: str, schedule_time: str, weekday: str, monthday: str, scheduled_at: str) -> str:
    if task_kind == "oneshot":
        return f"ONCE {scheduled_at}".strip()
    hour, minute = _parse_time_hm(schedule_time)
    if schedule_mode == "weekly":
        cron_dow = str((int(weekday or "1") + 6) % 7)
        return f"{minute} {hour} * * {cron_dow}"
    if schedule_mode == "monthly":
        day = min(28, max(1, int(monthday or "1")))
        return f"{minute} {hour} {day} * *"
    return f"{minute} {hour} * * *"


def _schedule_struct_for_task(task: dict[str, Any]) -> dict[str, Any]:
    source_meta = task.get("sourceMeta") or {}
    task_kind = str(source_meta.get("taskKind") or "normal").strip().lower()
    schedule_mode = str(source_meta.get("scheduleMode") or "daily").strip().lower()
    schedule_time = str(source_meta.get("scheduleTime") or "09:00").strip()
    weekday = str(source_meta.get("scheduleWeekday") or "1").strip()
    monthday = str(source_meta.get("scheduleMonthday") or "1").strip()
    scheduled_at = str(source_meta.get("scheduledAt") or "").strip()
    label = str(source_meta.get("scheduleLabel") or task.get("output") or "定时任务").strip() or "定时任务"
    return {
        "kind": task_kind,
        "mode": schedule_mode,
        "time": schedule_time,
        "weekday": weekday,
        "monthday": monthday,
        "at": scheduled_at,
        "expr": _cron_expr_for_task(task_kind, schedule_mode, schedule_time, weekday, monthday, scheduled_at),
        "tz": "Asia/Shanghai",
        "label": label,
    }


def _candidate_daily(now_local: dt.datetime, hour: int, minute: int) -> dt.datetime:
    return now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _candidate_weekly(now_local: dt.datetime, hour: int, minute: int, weekday: int) -> dt.datetime:
    base = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta_days = weekday - base.weekday()
    return base + dt.timedelta(days=delta_days)


def _candidate_monthly(now_local: dt.datetime, hour: int, minute: int, monthday: int) -> dt.datetime:
    safe_day = min(28, max(1, monthday))
    return now_local.replace(day=safe_day, hour=hour, minute=minute, second=0, microsecond=0)


def compute_next_run_at_ms(schedule: dict[str, Any], *, now_ms: int | None = None, created_ms: int | None = None, first_run: bool = False) -> int | None:
    now_ms = int(now_ms or _now_ms())
    kind = str(schedule.get("kind") or "").strip().lower()
    if kind == "oneshot":
        target = _parse_any_time_ms(schedule.get("at"))
        if not target:
            return None
        if first_run:
            return target
        return None

    now_local = dt.datetime.fromtimestamp(now_ms / 1000, tz=dt.timezone.utc).astimezone(SH_TZ)
    hour, minute = _parse_time_hm(str(schedule.get("time") or "09:00"))
    mode = str(schedule.get("mode") or "daily").strip().lower()
    if mode == "weekly":
        candidate = _candidate_weekly(now_local, hour, minute, min(6, max(0, int(schedule.get("weekday") or "1") - 1)))
        step = dt.timedelta(days=7)
    elif mode == "monthly":
        candidate = _candidate_monthly(now_local, hour, minute, int(schedule.get("monthday") or "1"))
        step = dt.timedelta(days=31)
    else:
        candidate = _candidate_daily(now_local, hour, minute)
        step = dt.timedelta(days=1)

    candidate_ms = int(candidate.astimezone(dt.timezone.utc).timestamp() * 1000)
    if first_run:
        if created_ms and created_ms <= candidate_ms <= now_ms:
            return candidate_ms
        while candidate_ms < now_ms:
            candidate = candidate + step
            if mode == "monthly":
                next_month = candidate.month + 1
                year = candidate.year + (1 if next_month == 13 else 0)
                month = 1 if next_month == 13 else next_month
                candidate = candidate.replace(year=year, month=month, day=min(28, max(1, int(schedule.get("monthday") or "1"))))
            candidate_ms = int(candidate.astimezone(dt.timezone.utc).timestamp() * 1000)
        return candidate_ms

    candidate = candidate + step
    if mode == "monthly":
        next_month = now_local.month + 1
        year = now_local.year + (1 if next_month == 13 else 0)
        month = 1 if next_month == 13 else next_month
        candidate = now_local.replace(year=year, month=month, day=min(28, max(1, int(schedule.get("monthday") or "1"))), hour=hour, minute=minute, second=0, microsecond=0)
    return int(candidate.astimezone(dt.timezone.utc).timestamp() * 1000)


def _load_jobs_payload() -> dict[str, Any]:
    ensure_cron_dirs()
    payload = atomic_json_read(CRON_JOBS_PATH, {"jobs": []})
    if not isinstance(payload, dict):
        return {"jobs": []}
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        payload["jobs"] = []
    return payload


def _job_id_for_task(task_id: str) -> str:
    return f"task-{str(task_id or '').strip()}"


def upsert_job_for_task(task: dict[str, Any]) -> str:
    ensure_cron_dirs()
    task_id = str(task.get("id") or "").strip()
    if not task_id:
        raise ValueError("task id required")
    source_meta = task.get("sourceMeta") or {}
    schedule = _schedule_struct_for_task(task)
    created_ms = _task_created_ms(task)
    job_id = str(source_meta.get("automationJobId") or "").strip() or _job_id_for_task(task_id)
    message = str(source_meta.get("rawRequest") or source_meta.get("userBrief") or task.get("title") or "").strip()

    def modifier(payload: dict[str, Any]) -> dict[str, Any]:
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            jobs = []
            payload = {"jobs": jobs}
        existing = next((item for item in jobs if isinstance(item, dict) and str(item.get("id") or "") == job_id), None)
        next_run_ms = compute_next_run_at_ms(schedule, created_ms=created_ms, first_run=True)
        if existing is None:
            existing = {
                "id": job_id,
                "name": str(task.get("title") or task_id),
                "taskId": task_id,
                "agentId": str(source_meta.get("dispatchAgent") or "chief_of_staff"),
                "enabled": True,
                "schedule": {},
                "payload": {},
                "delivery": {},
                "state": {},
            }
            jobs.append(existing)
        existing["name"] = str(task.get("title") or task_id)
        existing["taskId"] = task_id
        existing["agentId"] = str(source_meta.get("dispatchAgent") or existing.get("agentId") or "chief_of_staff")
        existing["enabled"] = True
        existing["schedule"] = schedule
        existing["payload"] = {
            "taskId": task_id,
            "title": str(task.get("title") or ""),
            "message": message,
            "flowMode": str(source_meta.get("flowMode") or ""),
        }
        existing["delivery"] = {
            "channel": "webchat",
            "to": task_id,
        }
        state = existing.get("state") if isinstance(existing.get("state"), dict) else {}
        state.setdefault("consecutiveErrors", 0)
        if not isinstance(state.get("lastRunAtMs"), (int, float)):
            state["lastRunAtMs"] = None
        if not isinstance(state.get("nextRunAtMs"), (int, float)):
            state["nextRunAtMs"] = next_run_ms
        state.setdefault("lastRunStatus", "pending")
        state.setdefault("lastDeliveryStatus", "pending")
        state["running"] = False
        existing["state"] = state
        payload["jobs"] = jobs
        return payload

    atomic_json_update(CRON_JOBS_PATH, modifier, {"jobs": []})
    return job_id


def sync_jobs_from_tasks(tasks: list[dict[str, Any]]) -> list[str]:
    changed: list[str] = []
    for task in tasks:
        source_meta = task.get("sourceMeta") or {}
        kind = str(source_meta.get("taskKind") or "").strip().lower()
        if kind not in {"oneshot", "recurring"}:
            continue
        changed.append(upsert_job_for_task(task))
    return changed


def read_jobs() -> list[dict[str, Any]]:
    return list(_load_jobs_payload().get("jobs") or [])


def set_job_enabled(job_id: str, enabled: bool) -> dict[str, Any]:
    ensure_cron_dirs()
    snapshot: dict[str, Any] = {}

    def modifier(payload: dict[str, Any]) -> dict[str, Any]:
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            payload = {"jobs": []}
            return payload
        for job in jobs:
            if not isinstance(job, dict) or str(job.get("id") or "") != str(job_id or "").strip():
                continue
            job["enabled"] = bool(enabled)
            state = job.get("state") if isinstance(job.get("state"), dict) else {}
            state["running"] = False
            if enabled:
                schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
                state["nextRunAtMs"] = compute_next_run_at_ms(schedule, first_run=False)
                state["lastRunStatus"] = str(state.get("lastRunStatus") or "pending")
            else:
                state["nextRunAtMs"] = None
                state["lastRunStatus"] = "cancelled"
                state["lastDeliveryStatus"] = "cancelled"
            job["state"] = state
            snapshot.update(copy.deepcopy(job))
            break
        return payload

    atomic_json_update(CRON_JOBS_PATH, modifier, {"jobs": []})
    return snapshot


def claim_due_jobs(now_ms: int | None = None) -> list[dict[str, Any]]:
    ensure_cron_dirs()
    now_ms = int(now_ms or _now_ms())
    claimed: list[dict[str, Any]] = []

    def modifier(payload: dict[str, Any]) -> dict[str, Any]:
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            payload = {"jobs": []}
            return payload
        for job in jobs:
            if not isinstance(job, dict) or not job.get("enabled", True):
                continue
            state = job.get("state") if isinstance(job.get("state"), dict) else {}
            next_run_ms = state.get("nextRunAtMs")
            if not isinstance(next_run_ms, (int, float)) or int(next_run_ms) <= 0:
                continue
            if bool(state.get("running")):
                continue
            if int(next_run_ms) > now_ms:
                continue
            state["running"] = True
            state["lastClaimedAtMs"] = now_ms
            job["state"] = state
            claimed.append(copy.deepcopy(job))
        return payload

    atomic_json_update(CRON_JOBS_PATH, modifier, {"jobs": []})
    return claimed


def append_run_event(job_id: str, event: dict[str, Any]) -> None:
    ensure_cron_dirs()
    path = CRON_RUNS_DIR / f"{job_id}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def finalize_job_run(job_id: str, *, status: str, delivery_status: str = "queued", summary: str = "", error: str = "", run_at_ms: int | None = None) -> dict[str, Any]:
    ensure_cron_dirs()
    run_at_ms = int(run_at_ms or _now_ms())
    snapshot: dict[str, Any] = {}

    def modifier(payload: dict[str, Any]) -> dict[str, Any]:
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(jobs, list):
            payload = {"jobs": []}
            return payload
        for job in jobs:
            if not isinstance(job, dict) or str(job.get("id") or "") != job_id:
                continue
            schedule = job.get("schedule") if isinstance(job.get("schedule"), dict) else {}
            state = job.get("state") if isinstance(job.get("state"), dict) else {}
            state["running"] = False
            state["lastRunAtMs"] = run_at_ms
            state["lastRunStatus"] = status
            state["lastDeliveryStatus"] = delivery_status
            state["lastDurationMs"] = 0
            if error:
                state["consecutiveErrors"] = int(state.get("consecutiveErrors") or 0) + 1
            else:
                state["consecutiveErrors"] = 0
            if str(schedule.get("kind") or "") == "oneshot":
                state["nextRunAtMs"] = None
                job["enabled"] = False
            else:
                state["nextRunAtMs"] = compute_next_run_at_ms(schedule, now_ms=run_at_ms, first_run=False)
            job["state"] = state
            snapshot.update(copy.deepcopy(job))
            break
        return payload

    atomic_json_update(CRON_JOBS_PATH, modifier, {"jobs": []})
    append_run_event(
        job_id,
        {
            "ts": run_at_ms,
            "runAtMs": run_at_ms,
            "status": status,
            "deliveryStatus": delivery_status,
            "summary": summary,
            "error": error,
        },
    )
    return snapshot

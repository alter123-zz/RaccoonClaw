#!/usr/bin/env python3
import json, pathlib, datetime, logging, re
from file_lock import atomic_json_write, atomic_json_read
from runtime_paths import canonical_data_dir, canonical_deliverables_root
from task_ids import NORMAL_TASK_ID_RE
from task_store_repair import repair_task_store
from utils import beijing_now, format_beijing, read_json, today_str
from automation_health import build_automation_snapshot
from blocker_utils import summarize_task_blocker
from workbench_modes import inject_mode_id

log = logging.getLogger('refresh')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

BASE = pathlib.Path(__file__).parent.parent
DATA = canonical_data_dir()
OCLAW_HOME = pathlib.Path.home() / '.openclaw'
CANONICAL_DELIVERABLES_ROOT = canonical_deliverables_root()
_ARTIFACT_DIRS = ('deliverables', 'reports', 'outputs', 'artifacts')
_GENERIC_OUTPUT_BASENAMES = {'tasks_source.json', 'tasks.json', 'live_status.json'}


def output_meta(path):
    p = pathlib.Path(path)
    if not p.exists():
        return {"exists": False, "lastModified": None}
    ts = format_beijing(p.stat().st_mtime)
    return {"exists": True, "lastModified": ts}


def _parse_ts(raw) -> float | None:
    if raw in (None, ''):
        return None
    try:
        if isinstance(raw, (int, float)):
            value = float(raw)
            return value / 1000 if value > 10_000_000_000 else value
        return datetime.datetime.fromisoformat(str(raw).replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def _task_created_ts(task: dict) -> float | None:
    flow_log = task.get('flow_log') or []
    if isinstance(flow_log, list):
        for entry in flow_log:
            if isinstance(entry, dict):
                ts = _parse_ts(entry.get('at'))
                if ts is not None:
                    return ts
    return _parse_ts(task.get('updatedAt'))


def _read_preview(path: pathlib.Path, max_chars: int = 600) -> str:
    try:
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + '…'


def _looks_like_generic_output(raw: str) -> bool:
    raw = str(raw or '').strip()
    if not raw:
        return True
    path = pathlib.Path(raw)
    if path.name in _GENERIC_OUTPUT_BASENAMES:
        return True
    generic_dir = DATA
    try:
        return path.exists() and generic_dir in path.resolve().parents
    except Exception:
        return False


def discover_task_artifacts() -> dict[str, list[dict]]:
    artifacts_by_task: dict[str, list[dict]] = {}
    for workspace in OCLAW_HOME.glob('workspace-*'):
        agent_id = workspace.name.replace('workspace-', '')
        candidate_folders: list[pathlib.Path] = []
        for folder_name in _ARTIFACT_DIRS:
            candidate_folders.append(workspace / folder_name)
            candidate_folders.append(workspace / 'data' / folder_name)
        seen_folders: set[pathlib.Path] = set()
        for folder in candidate_folders:
            try:
                resolved_folder = folder.resolve()
            except Exception:
                resolved_folder = folder
            if resolved_folder in seen_folders or not folder.exists():
                continue
            seen_folders.add(resolved_folder)
            for path in folder.rglob('*'):
                if not path.is_file():
                    continue
                match = NORMAL_TASK_ID_RE.search(path.name)
                if not match:
                    continue
                task_id = match.group(0)
                artifacts_by_task.setdefault(task_id, []).append({
                    'path': str(path),
                    'name': path.name,
                    'agentId': agent_id,
                    'folder': folder.name,
                    'isCanonical': CANONICAL_DELIVERABLES_ROOT in path.parents,
                    'mtime': path.stat().st_mtime,
                    'lastModified': format_beijing(path.stat().st_mtime),
                    'preview': _read_preview(path),
                })
    for task_id, items in artifacts_by_task.items():
        items.sort(
            key=lambda item: (
                1 if item.get('isCanonical') else 0,
                str(item.get('lastModified') or ''),
            ),
            reverse=True,
        )
        artifacts_by_task[task_id] = items
    return artifacts_by_task


def _automation_task_id(job: dict) -> str:
    raw = re.sub(r'[^A-Za-z0-9]+', '', str(job.get('id') or 'AUTO'))[:8].upper() or 'AUTO'
    return f'JJC-AUTO-{raw}'


def _automation_org_label(job: dict) -> str:
    if str(job.get('agentId') or '') == 'chief_of_staff':
        return '总裁办'
    if str(job.get('routeLabel') or '').strip():
        return str(job.get('routeLabel') or '').split('·')[0].strip()
    return '自动化'


def build_automation_tasks(snapshot: dict | None) -> list[dict]:
    jobs = (snapshot or {}).get('jobs') or []
    checked_at = str((snapshot or {}).get('checkedAt') or '')
    tasks: list[dict] = []
    for job in jobs:
        status = str(job.get('status') or 'healthy')
        enabled = bool(job.get('enabled'))
        state = 'Doing'
        block = '无'
        now = str(job.get('message') or '运行正常')
        if not enabled or status == 'paused':
            state = 'Blocked'
            now = '任务已暂停'
            block = '任务已暂停'
        elif status in {'critical', 'warning'}:
            state = 'Blocked'
            block = str(job.get('lastError') or job.get('message') or '自动化异常')
        elif status == 'pending':
            state = 'Doing'
            now = str(job.get('message') or '等待首次执行')

        schedule_label = str(job.get('scheduleLabel') or job.get('scheduleExpr') or '定时任务')
        route_label = str(job.get('routeLabel') or '自动化')
        flow_log = []
        if job.get('lastRunAt'):
            flow_log.append({
                'at': str(job.get('lastRunAt')),
                'from': route_label,
                'to': _automation_org_label(job),
                'remark': f"最近执行：{job.get('lastRunStatus') or 'ok'} / {job.get('message') or '运行正常'}",
            })
        if job.get('nextRunAt'):
            flow_log.append({
                'at': str(job.get('nextRunAt')),
                'from': '调度器',
                'to': _automation_org_label(job),
                'remark': f"下一次执行：{schedule_label}",
            })
        if not flow_log and checked_at:
            flow_log.append({
                'at': checked_at,
                'from': '调度器',
                'to': _automation_org_label(job),
                'remark': f"已纳入自动化监测：{schedule_label}",
            })

        tasks.append({
            'id': _automation_task_id(job),
            'title': str(job.get('name') or '自动化任务'),
            'official': '自动化任务',
            'org': _automation_org_label(job),
            'state': state,
            'now': now,
            'eta': format_beijing(job.get('nextRunAt') or '', '%Y-%m-%d %H:%M') if job.get('nextRunAt') else '-',
            'block': block,
            'output': schedule_label,
            'ac': '保持按计划执行并在异常时回传',
            'flow_log': flow_log,
            'updatedAt': str(job.get('lastRunAt') or checked_at or ''),
            'archived': False,
            'review_round': 0,
            'todos': [],
            'heartbeat': {
                'status': 'active' if enabled and status in {'healthy', 'pending'} else 'warn' if status == 'warning' else 'stalled' if status in {'critical', 'paused'} or not enabled else 'unknown',
                'label': f"⏰ {job.get('message') or '自动化任务'}",
                'ageSec': 0,
            },
            'scheduler': {
                'enabled': True,
            },
            'sourceMeta': {
                'kind': 'automation_job',
                'automationJobId': str(job.get('id') or ''),
                'scheduleLabel': schedule_label,
                'scheduleExpr': str(job.get('scheduleExpr') or ''),
                'routeLabel': route_label,
                'routeMode': str(job.get('routeMode') or ''),
                'channel': str(job.get('channel') or ''),
                'target': str(job.get('target') or ''),
                'status': status,
                'enabled': enabled,
                'lastRunAt': job.get('lastRunAt'),
                'nextRunAt': job.get('nextRunAt'),
                'lastRunStatus': str(job.get('lastRunStatus') or ''),
                'lastDeliveryStatus': str(job.get('lastDeliveryStatus') or ''),
                'lastDurationMs': job.get('lastDurationMs'),
                'lastError': str(job.get('lastError') or ''),
            },
        })
    return tasks


def main():
    repair_task_store()
    # 使用 officials_stats.json（与 sync_officials_stats.py 统一）
    officials_data = read_json(DATA / 'officials_stats.json', {})
    officials = officials_data.get('officials', []) if isinstance(officials_data, dict) else officials_data
    # 任务源优先：tasks_source.json（可对接外部系统同步写入）
    tasks = atomic_json_read(DATA / 'tasks_source.json', [])
    if not tasks:
        tasks = read_json(DATA / 'tasks.json', [])

    sync_status = read_json(DATA / 'sync_status.json', {})
    artifacts_by_task = discover_task_artifacts()

    org_map = {}
    for o in officials:
        label = o.get('label', o.get('name', ''))
        if label:
            org_map[label] = label

    now_ts = datetime.datetime.now(datetime.timezone.utc)
    automation_snapshot = build_automation_snapshot()
    automation_jobs_by_id = {
        str(job.get('id') or ''): job
        for job in (automation_snapshot.get('jobs') or [])
        if isinstance(job, dict)
    }

    for t in tasks:
        inject_mode_id(t)
        t['org'] = t.get('org') or org_map.get(t.get('official', ''), '')
        output_artifacts = artifacts_by_task.get(str(t.get('id') or ''), [])
        task_created_ts = _task_created_ts(t)
        if task_created_ts is not None:
            filtered_artifacts = [
                item for item in output_artifacts
                if float(item.get('mtime') or 0) >= task_created_ts - 60
            ]
            if filtered_artifacts:
                output_artifacts = filtered_artifacts
        t['outputArtifacts'] = output_artifacts
        raw_output = str(t.get('output') or '')
        resolved_output = raw_output
        if output_artifacts and (_looks_like_generic_output(raw_output) or not pathlib.Path(raw_output).exists()):
            resolved_output = str(output_artifacts[0].get('path') or '')
        t['resolvedOutput'] = resolved_output
        t['outputMeta'] = output_meta(resolved_output or raw_output)
        blocker_feedback = summarize_task_blocker(t)
        if blocker_feedback:
            t['blockerFeedback'] = blocker_feedback
        source_meta = t.get('sourceMeta') or {}
        if isinstance(source_meta, dict):
            job_id = str(source_meta.get('automationJobId') or '').strip()
            if job_id:
                job = automation_jobs_by_id.get(job_id) or {}
                next_run_at = str(job.get('nextRunAt') or '').strip()
                if next_run_at:
                    t['eta'] = format_beijing(next_run_at, '%Y-%m-%d %H:%M')
                source_meta['scheduleExpr'] = str(job.get('scheduleExpr') or source_meta.get('scheduleExpr') or '')
                source_meta['scheduleLabel'] = str(job.get('scheduleLabel') or source_meta.get('scheduleLabel') or '')
                source_meta['nextRunAt'] = next_run_at
                source_meta['lastRunAt'] = str(job.get('lastRunAt') or source_meta.get('lastRunAt') or '')
                source_meta['lastRunStatus'] = str(job.get('lastRunStatus') or source_meta.get('lastRunStatus') or '')
                source_meta['lastDeliveryStatus'] = str(job.get('lastDeliveryStatus') or source_meta.get('lastDeliveryStatus') or '')
                source_meta['lastDurationMs'] = job.get('lastDurationMs') if job.get('lastDurationMs') is not None else source_meta.get('lastDurationMs')
                source_meta['lastError'] = str(job.get('lastError') or source_meta.get('lastError') or '')
                source_meta['jobEnabled'] = bool(job.get('enabled')) if job.get('enabled') is not None else bool(source_meta.get('jobEnabled'))
                source_meta['jobRunning'] = bool(job.get('running')) if job.get('running') is not None else bool(source_meta.get('jobRunning'))

        # 心跳时效检测：对执行中的正式任务和 OpenClaw 运行会话标注活跃度。
        # OC-* 会话在 state=Review/Next 时通常表示“最近活跃，但当前空闲”，
        # 不应该继续被标成“停滞”。
        if t.get('state') in ('Doing', 'Assigned', 'Review'):
            updated_raw = t.get('updatedAt') or t.get('sourceMeta', {}).get('updatedAt')
            age_sec = None
            if updated_raw:
                try:
                    if isinstance(updated_raw, (int, float)):
                        updated_dt = datetime.datetime.fromtimestamp(updated_raw / 1000, tz=datetime.timezone.utc)
                    else:
                        updated_dt = datetime.datetime.fromisoformat(str(updated_raw).replace('Z', '+00:00'))
                    age_sec = (now_ts - updated_dt).total_seconds()
                except Exception:
                    pass
            task_id = str(t.get('taskId') or t.get('id') or '')
            is_oc_session = task_id.startswith('OC-')
            session_state = str(t.get('state') or '')
            scheduled_kind = str(source_meta.get('taskKind') if isinstance(source_meta, dict) else '' or '').strip().lower()
            next_run_raw = str(source_meta.get('nextRunAt') if isinstance(source_meta, dict) else '' or '').strip()
            next_run_dt = None
            if next_run_raw:
                try:
                    next_run_dt = datetime.datetime.fromisoformat(next_run_raw.replace('Z', '+00:00'))
                except Exception:
                    next_run_dt = None

            if age_sec is None:
                t['heartbeat'] = {'status': 'unknown', 'label': '⚪ 未知', 'ageSec': None}
            elif scheduled_kind in {'oneshot', 'recurring'} and str(t.get('org') or '') == '调度器' and next_run_dt is not None:
                secs_until = max(0, int((next_run_dt - now_ts).total_seconds()))
                if secs_until <= 3600:
                    t['heartbeat'] = {'status': 'active', 'label': f'⏰ 将在 {max(1, secs_until // 60)} 分钟后执行', 'ageSec': int(age_sec)}
                else:
                    t['heartbeat'] = {'status': 'idle', 'label': f"🗓️ 下次执行 {format_beijing(next_run_raw, '%m-%d %H:%M')}", 'ageSec': int(age_sec)}
            elif is_oc_session and session_state in {'Review', 'Next'}:
                t['heartbeat'] = {'status': 'idle', 'label': f'⚪ 空闲 {int(age_sec//60)}分钟前', 'ageSec': int(age_sec)}
            elif age_sec < 180:
                t['heartbeat'] = {'status': 'active', 'label': f'🟢 活跃 {int(age_sec//60)}分钟前', 'ageSec': int(age_sec)}
            elif age_sec < 600:
                t['heartbeat'] = {'status': 'warn', 'label': f'🟡 可能停滞 {int(age_sec//60)}分钟前', 'ageSec': int(age_sec)}
            else:
                t['heartbeat'] = {'status': 'stalled', 'label': f'🔴 已停滞 {int(age_sec//60)}分钟', 'ageSec': int(age_sec)}
        else:
            t['heartbeat'] = None

    beijing_today = today_str('%Y-%m-%d')
    def _is_today_done(t):
        if t.get('state') != 'Done':
            return False
        ua = t.get('updatedAt', '')
        if format_beijing(ua, '%Y-%m-%d') == beijing_today:
            return True
        # fallback: outputMeta lastModified
        lm = t.get('outputMeta', {}).get('lastModified', '')
        if format_beijing(lm, '%Y-%m-%d') == beijing_today:
            return True
        return False
    today_done = sum(1 for t in tasks if _is_today_done(t))
    total_done = sum(1 for t in tasks if t.get('state') == 'Done')
    in_progress = sum(1 for t in tasks if t.get('state') in ['Doing', 'Review', 'Next', 'Blocked'])
    blocked = sum(1 for t in tasks if t.get('state') == 'Blocked')

    history = []
    for t in tasks:
        if t.get('state') == 'Done':
            lm = t.get('outputMeta', {}).get('lastModified')
            history.append({
                'at': lm or '未知',
                'official': t.get('official'),
                'task': t.get('title'),
                'out': t.get('resolvedOutput') or t.get('output'),
                'qa': '通过' if t.get('outputMeta', {}).get('exists') else '待补成果'
            })

    sync_ok = None
    if isinstance(sync_status, dict) and 'ok' in sync_status:
        sync_ok = sync_status.get('ok')

    automation_tasks = build_automation_tasks(automation_snapshot)
    repair_report = read_json(DATA / 'task_store_repair_report.json', {})

    payload = {
        'generatedAt': beijing_now().strftime('%Y-%m-%d %H:%M:%S'),
        'taskSource': 'tasks_source.json' if (DATA / 'tasks_source.json').exists() else 'tasks.json',
        'officials': officials,
        'tasks': [*automation_tasks, *tasks],
        'automation': automation_snapshot,
        'history': history,
        'metrics': {
            'officialCount': len(officials),
            'todayDone': today_done,
            'totalDone': total_done,
            'inProgress': in_progress,
            'blocked': blocked
        },
        'syncStatus': sync_status,
        'repairReport': repair_report,
        'health': {
            'syncOk': sync_ok,
            'syncLatencyMs': sync_status.get('durationMs'),
            'missingFieldCount': len(sync_status.get('missingFields', {})),
        }
    }

    atomic_json_write(DATA / 'live_status.json', payload)
    log.info(f'updated live_status.json ({len(tasks)} tasks)')


if __name__ == '__main__':
    main()

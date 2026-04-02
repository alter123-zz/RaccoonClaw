#!/usr/bin/env python3
"""
看板任务更新工具 - 供各团队 Agent 调用
"""
import argparse
import datetime
import json
import logging
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import zipfile

_BASE = pathlib.Path(__file__).resolve().parent.parent
from runtime_paths import canonical_data_dir, canonical_deliverables_root, canonical_task_deliverables_dir
from review_readiness import evaluate_review_readiness
from blocker_utils import detect_blocker_report

TASKS_FILE = canonical_data_dir() / 'tasks_source.json'
REFRESH_SCRIPT = _BASE / 'scripts' / 'refresh_live_data.py'
CANONICAL_DELIVERABLES_ROOT = canonical_deliverables_root()
OCLAW_HOME = pathlib.Path.home() / '.openclaw'
_ARTIFACT_DIRS = ('deliverables', 'reports', 'outputs', 'artifacts')
_TEXT_OUTPUT_EXTENSIONS = {'.txt', '.md', '.markdown', '.json', '.csv', '.tsv', '.html', '.htm', '.xml', '.yaml', '.yml'}
_HEADING_PREFIX_RE = re.compile(r'^\s*(?:第[一二三四五六七八九十百零0-9]+(?:部分|章|节)[：:]\s*|[一二三四五六七八九十百零0-9]+[、.]\s*)')
_OUTPUT_FILE_LINE_RE = re.compile(
    r'^\s*(?:[-*]\s*)?(?:(?P<label>[^:\n]+?)\s*\n?\s*→\s*|→\s*)?(?P<path>(?:/[^ \n]+|workspace-[^ \n]+))\s*$',
    re.MULTILINE,
)
_OUTPUT_PATH_TOKEN_RE = re.compile(
    r'(?P<path>(?:/[^ \n`]+|workspace-[^ \n`]+|(?:deliverables|reports|outputs|artifacts)/[^ \n`]+))'
)

log = logging.getLogger('kanban')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

from file_lock import atomic_json_read, atomic_json_update, atomic_json_write

STATE_ORG_MAP = {
    'ChiefOfStaff': '总裁办', 'Planning': '产品规划部', 'ReviewControl': '评审质控部', 'Assigned': '交付运营部',
    'Doing': '执行中', 'Review': '交付运营部', 'Done': '完成', 'Blocked': '阻塞',
}

TODO_STATUS_ALIASES = {
    'todo': 'pending',
    'pending': 'pending',
    'not-started': 'pending',
    'not_started': 'pending',
    'open': 'pending',
    'in-progress': 'in-progress',
    'in_progress': 'in-progress',
    'doing': 'in-progress',
    'active': 'in-progress',
    'completed': 'completed',
    'complete': 'completed',
    'done': 'completed',
    'closed': 'completed',
    'blocked': 'blocked',
}

AGENT_LABELS = {
    'chief_of_staff': '总裁办',
    'planning': '产品规划部',
    'review_control': '评审质控部',
    'delivery_ops': '交付运营部',
    'brand_content': '品牌内容部',
    'business_analysis': '经营分析部',
    'secops': '安全运维部',
    'compliance_test': '合规测试部',
    'engineering': '工程研发部',
    'people_ops': '人力组织部',
}

_CALLBACK_TODO_KEYWORDS = (
    '回传总裁办',
    '结果回传',
    '回传需求方',
    '回传',
)

def _ensure_scheduler(task):
    sched = task.setdefault('_scheduler', {})
    if not isinstance(sched, dict): sched = {}; task['_scheduler'] = sched
    sched.setdefault('enabled', True)
    sched.setdefault('stallThresholdSec', 180)
    sched.setdefault('maxRetry', 1)
    sched.setdefault('retryCount', 0)
    sched.setdefault('escalationLevel', 0)
    sched.setdefault('autoRollback', True)
    sched.setdefault('lastProgressAt', task.get('updatedAt') or now_iso())
    return sched

def _mark_scheduler_progress(task, dispatch_status=None):
    sched = _ensure_scheduler(task)
    sched['lastProgressAt'] = now_iso()
    sched['stallSince'] = None
    sched['retryCount'] = 0
    sched['escalationLevel'] = 0

def _normalize_todo_status(raw: str) -> str:
    return TODO_STATUS_ALIASES.get(str(raw or '').strip().lower(), 'pending')

def _now_label() -> str:
    return datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')

def _infer_agent_id() -> str:
    cwd = pathlib.Path.cwd()
    for candidate in (cwd, cwd.resolve()):
        name = candidate.name
        if name.startswith('workspace-'):
            return name.replace('workspace-', '', 1) or 'chief_of_staff'
        if candidate.parent.name == 'agents':
            return name or 'chief_of_staff'
    env_agent = str(os.environ.get('OPENCLAW_AGENT_ID') or '').strip()
    if env_agent:
        return env_agent
    return 'chief_of_staff'

def _agent_label(agent_id: str | None = None) -> str:
    return AGENT_LABELS.get(str(agent_id or _infer_agent_id()).strip(), str(agent_id or _infer_agent_id()).strip() or '专项团队')

def _append_progress_snapshot(task, *, text=None, todos=None, agent_id=None):
    progress_log = task.setdefault('progress_log', [])
    if not isinstance(progress_log, list):
        progress_log = []
        task['progress_log'] = progress_log
    snapshot = {
        'at': now_iso(),
        'agent': str(agent_id or _infer_agent_id()),
        'agentLabel': _agent_label(agent_id),
        'state': task.get('state', ''),
        'org': task.get('org', ''),
    }
    if text:
        snapshot['text'] = str(text).strip()
    if todos is not None:
        snapshot['todos'] = todos
    progress_log.append(snapshot)
    return snapshot

def _source_meta(task):
    source_meta = task.get('sourceMeta') or {}
    return source_meta if isinstance(source_meta, dict) else {}

def _required_stages(task) -> list[str]:
    raw = _source_meta(task).get('requiredStages') or []
    if not isinstance(raw, list):
        return []
    return [str(item).strip().lower() for item in raw if str(item).strip()]

def _is_full_flow_task(task) -> bool:
    flow_mode = str(_source_meta(task).get('flowMode') or '').strip().lower()
    return flow_mode == 'full' or _required_stages(task) == ['planning', 'review', 'dispatch', 'execution']

def _task_todos(task) -> list[dict]:
    todos = task.get('todos') or []
    return todos if isinstance(todos, list) else []

def _is_completed_status(value: str) -> bool:
    return _normalize_todo_status(value) == 'completed'

def _has_incomplete_callback_todo(task) -> bool:
    for item in _task_todos(task):
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or '').strip()
        if any(keyword in title for keyword in _CALLBACK_TODO_KEYWORDS):
            return not _is_completed_status(str(item.get('status') or ''))
    return False

def _done_transition_guard(task) -> str:
    if not _is_full_flow_task(task):
        return ''
    if _has_incomplete_callback_todo(task):
        return 'full 流程任务尚未完成“回传总裁办”，禁止直接标记 Done'
    return ''

def _is_terminal_state(task) -> bool:
    return str(task.get('state') or '').strip() in {'Done', 'Cancelled'}

def _is_callback_todo_title(title: str) -> bool:
    raw = str(title or '').strip()
    return bool(raw) and any(keyword in raw for keyword in _CALLBACK_TODO_KEYWORDS)

def _coerce_todos_for_terminal_task(task, todos: list[dict]) -> list[dict]:
    if not _is_terminal_state(task):
        return todos

    existing_by_id = {
        str(item.get('id') or '').strip(): item
        for item in _task_todos(task)
        if isinstance(item, dict) and str(item.get('id') or '').strip()
    }

    coerced: list[dict] = []
    for item in todos:
        normalized = dict(item)
        todo_id = str(normalized.get('id') or '').strip()
        title = str(normalized.get('title') or '').strip()
        existing = existing_by_id.get(todo_id)
        if existing and _is_completed_status(str(existing.get('status') or '')):
            normalized['status'] = 'completed'
        if _is_callback_todo_title(title):
            normalized['status'] = 'completed'
            normalized.setdefault('detail', '终态保护：已保持回传总裁办为完成状态。')
        coerced.append(normalized)

    if not any(_is_callback_todo_title(str(item.get('title') or '')) for item in coerced):
        for existing in _task_todos(task):
            if not isinstance(existing, dict):
                continue
            if _is_callback_todo_title(str(existing.get('title') or '')):
                normalized = dict(existing)
                normalized['status'] = 'completed'
                coerced.append(normalized)
                break
    return coerced

def _normalize_terminal_now(task, now_text: str) -> str:
    text = str(now_text or '').strip()
    if not _is_terminal_state(task):
        return text
    if not text or '回传总裁办' in text or '执行完成' in text or '整理摘要' in text:
        return '已完成：回传总裁办' if str(task.get('state') or '').strip() == 'Done' else text
    return text

def _parse_plan_steps(plan_text: str) -> list[dict]:
    parts = [part.strip() for part in str(plan_text or '').split('|')]
    todos: list[dict] = []
    for idx, part in enumerate(parts, start=1):
        if not part:
            continue
        status = 'pending'
        title = part
        if '🔄' in part:
            status = 'in-progress'
            title = part.replace('🔄', '').strip()
        elif '✅' in part:
            status = 'completed'
            title = part.replace('✅', '').strip()
        elif '⛔' in part or '🚫' in part:
            status = 'blocked'
            title = part.replace('⛔', '').replace('🚫', '').strip()
        todos.append({
            'id': str(idx),
            'title': title or f'步骤{idx}',
            'status': status,
        })
    return todos

def _deliverable_filename(task_id: str, suffix: str = '交付纪要') -> str:
    safe_suffix = re.sub(r'[\\/:*?"<>|]+', '-', str(suffix or '交付纪要')).strip(' .') or '交付纪要'
    return f'{task_id}_{safe_suffix}.md'

def _write_text_deliverable(task_id: str, output_text: str, summary: str = '') -> pathlib.Path:
    dst_dir = canonical_task_deliverables_dir(task_id)
    filename = _deliverable_filename(task_id, summary or '交付纪要')
    dst = dst_dir / filename
    body = str(output_text or '').strip()
    summary_text = str(summary or '').strip()
    lines = [
        f'# {task_id} 交付纪要',
        '',
        f'- 生成时间：{_now_label()}',
        f'- 执行部门：{_agent_label()}',
    ]
    if summary_text:
        lines.append(f'- 摘要：{summary_text}')
    lines.extend(['', '## 交付内容', '', body or '（无正文）', ''])
    dst.write_text('\n'.join(lines), encoding='utf-8')
    return dst

def _resolve_referenced_output_path(raw_path: str) -> pathlib.Path | None:
    raw = str(raw_path or '').strip()
    if not raw:
        return None
    candidate = pathlib.Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate if candidate.exists() else None
    if raw.startswith('workspace-'):
        candidate = OCLAW_HOME / raw
        return candidate if candidate.exists() else None
    if any(raw.startswith(f'{prefix}/') for prefix in _ARTIFACT_DIRS):
        candidate = pathlib.Path.cwd() / raw
        return candidate.resolve() if candidate.exists() else None
    return None

def _extract_referenced_outputs(output_text: str) -> list[dict]:
    results: list[dict] = []
    seen: set[str] = set()
    for match in _OUTPUT_FILE_LINE_RE.finditer(str(output_text or '')):
        raw_path = str(match.group('path') or '').strip()
        resolved = _resolve_referenced_output_path(raw_path)
        if resolved is None or not resolved.is_file():
            continue
        key = str(resolved.resolve())
        if key in seen:
            continue
        seen.add(key)
        label = str(match.group('label') or '').strip()
        results.append({
            'label': label,
            'raw_path': raw_path,
            'path': resolved.resolve(),
        })
    for match in _OUTPUT_PATH_TOKEN_RE.finditer(str(output_text or '')):
        raw_path = str(match.group('path') or '').strip().rstrip('.,);]')
        resolved = _resolve_referenced_output_path(raw_path)
        if resolved is None or not resolved.is_file():
            continue
        key = str(resolved.resolve())
        if key in seen:
            continue
        seen.add(key)
        results.append({
            'label': '',
            'raw_path': raw_path,
            'path': resolved.resolve(),
        })
    return results

def _safe_read_text(src: pathlib.Path) -> str:
    try:
        return src.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return src.read_text(encoding='utf-8', errors='replace')

def _build_merged_deliverable(task_id: str, output_text: str, summary: str, referenced_outputs: list[dict]) -> pathlib.Path:
    dst_dir = canonical_task_deliverables_dir(task_id)
    filename = _deliverable_filename(task_id, summary or '汇总交付')
    dst = dst_dir / filename
    lines = [
        f'# {task_id} 汇总交付',
        '',
        f'- 生成时间：{_now_label()}',
        f'- 执行部门：{_agent_label()}',
    ]
    summary_text = str(summary or '').strip()
    if summary_text:
        lines.append(f'- 摘要：{summary_text}')
    lines.extend([
        '',
        '## 子产出清单',
        '',
    ])
    for item in referenced_outputs:
        title = item['label'] or item['path'].stem
        lines.extend([
            f'- {title}',
            f'  - 原始路径：`{item["raw_path"]}`',
        ])
    lines.extend([
        '',
        '## 汇编正文',
        '',
    ])
    for item in referenced_outputs:
        src = item['path']
        title = item['label'] or src.stem
        lines.extend([
            f'### {title}',
            '',
            f'- 原始路径：`{item["raw_path"]}`',
            '',
        ])
        if src.suffix.lower() in _TEXT_OUTPUT_EXTENSIONS:
            body = _safe_read_text(src).strip()
            lines.extend([body or '（文件为空）', ''])
        else:
            lines.extend(['（该文件为非文本产出，请查看原始文件）', ''])
    dst.write_text('\n'.join(lines), encoding='utf-8')
    return dst

def _materialize_output_text(task_id: str, output_text: str, summary: str = '') -> pathlib.Path:
    referenced_outputs = _extract_referenced_outputs(output_text)
    if len(referenced_outputs) == 1:
        return pathlib.Path(_materialize_task_outputs(task_id, str(referenced_outputs[0]['path'])))
    if len(referenced_outputs) >= 2:
        return _build_merged_deliverable(task_id, output_text, summary, referenced_outputs)
    return _write_text_deliverable(task_id, output_text, summary)

def _materialize_task_outputs(task_id: str, output_path: str) -> str:
    raw = str(output_path or '').strip()
    if not raw: return raw
    src = pathlib.Path(raw).expanduser()
    if not src.exists(): return raw
    dst_dir = canonical_task_deliverables_dir(task_id)
    dst = dst_dir / src.name
    if src.is_dir():
        if dst.exists(): shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists(): dst.unlink()
        shutil.copy2(src, dst)
    return str(dst.resolve())

def load(): return atomic_json_read(TASKS_FILE, [])

def save(tasks):
    atomic_json_write(TASKS_FILE, tasks)
    def _refresh():
        try:
            subprocess.run(
                [sys.executable, str(REFRESH_SCRIPT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
        except Exception:
            pass

    threading.Thread(target=_refresh, daemon=True).start()

def now_iso(): return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
def find_task(tasks, task_id): return next((t for t in tasks if t.get('id') == task_id), None)

def _coerce_output_path(task_id: str, output_value: str, summary: str = '') -> str:
    raw = str(output_value or '').strip()
    if not raw:
        return ''
    src = pathlib.Path(raw).expanduser()
    if src.exists():
        if src.is_file() and src.suffix.lower() in _TEXT_OUTPUT_EXTENSIONS:
            body = _safe_read_text(src)
            referenced_outputs = _extract_referenced_outputs(body)
            if len(referenced_outputs) >= 2:
                return str(_build_merged_deliverable(task_id, body, summary, referenced_outputs).resolve())
        return _materialize_task_outputs(task_id, raw)
    return str(_materialize_output_text(task_id, raw, summary).resolve())

def cmd_create(task_id, title, state, org, official, remark=None):
    def modifier(tasks):
        tasks = [t for t in tasks if t.get('id') != task_id]
        tasks.insert(0, {"id": task_id, "title": title, "official": official, "org": org, "state": state, "now": f"需求已创建", "updatedAt": now_iso()})
        return tasks
    atomic_json_update(TASKS_FILE, modifier, [])
    save(load()); return 0

def cmd_state(task_id, new_state, now_text=None):
    guard_error = {'message': ''}

    def modifier(tasks):
        t = find_task(tasks, task_id)
        if not t: return tasks
        if str(new_state or '').strip().lower() == 'done':
            guard_error['message'] = _done_transition_guard(t)
            if guard_error['message']:
                log.warning(f'⚠️ 拒绝将 {task_id} 直接标记为 Done：{guard_error["message"]}')
                return tasks
        t['state'] = new_state
        if new_state in STATE_ORG_MAP: t['org'] = STATE_ORG_MAP[new_state]
        if now_text: t['now'] = now_text
        t['updatedAt'] = now_iso(); return tasks
    atomic_json_update(TASKS_FILE, modifier, [])
    if guard_error['message']:
        print(f'[看板] 拒绝状态流转：{guard_error["message"]}', flush=True)
        return 2
    save(load()); return 0

def cmd_flow(task_id, from_dept, to_dept, remark):
    def modifier(tasks):
        t = find_task(tasks, task_id)
        if not t: return tasks
        t.setdefault('flow_log', []).append({"at": now_iso(), "from": from_dept, "to": to_dept, "remark": remark})
        t['updatedAt'] = now_iso(); return tasks
    atomic_json_update(TASKS_FILE, modifier, [])
    save(load()); return 0

def cmd_progress(task_id, now_text, plan_text):
    def modifier(tasks):
        t = find_task(tasks, task_id)
        if not t:
            return tasks
        todos = _parse_plan_steps(plan_text)
        t['now'] = _normalize_terminal_now(t, now_text) or t.get('now', '')
        if todos:
            t['todos'] = _coerce_todos_for_terminal_task(t, todos)
        t['updatedAt'] = now_iso()
        _append_progress_snapshot(t, text=t.get('now', ''), todos=t.get('todos') or None)
        _mark_scheduler_progress(t)
        return tasks
    atomic_json_update(TASKS_FILE, modifier, [])
    save(load()); return 0

def cmd_todo(task_id, todo_id, title, status, detail=None):
    def modifier(tasks):
        t = find_task(tasks, task_id)
        if not t:
            return tasks
        todos = t.setdefault('todos', [])
        if not isinstance(todos, list):
            todos = []
            t['todos'] = todos
        todo_key = str(todo_id).strip()
        normalized = {
            'id': todo_key,
            'title': str(title or '').strip() or f'步骤{todo_key or len(todos) + 1}',
            'status': _normalize_todo_status(status),
        }
        detail_text = str(detail or '').strip()
        if detail_text:
            normalized['detail'] = detail_text
        existing = next((item for item in todos if str(item.get('id', '')).strip() == todo_key), None)
        if _is_terminal_state(t):
            if existing and _is_completed_status(str(existing.get('status') or '')):
                normalized['status'] = 'completed'
            if _is_callback_todo_title(normalized['title']):
                normalized['status'] = 'completed'
                if not detail_text and existing and str(existing.get('detail') or '').strip():
                    normalized['detail'] = str(existing.get('detail') or '').strip()
        if existing is None:
            todos.append(normalized)
        else:
            existing.update(normalized)
        t['updatedAt'] = now_iso()
        if detail_text and normalized['status'] == 'completed':
            t['now'] = f"已完成：{normalized['title']}"
        elif _is_terminal_state(t):
            t['now'] = _normalize_terminal_now(t, t.get('now', ''))
        _append_progress_snapshot(t, text=t.get('now', ''), todos=todos)
        _mark_scheduler_progress(t)
        return tasks
    atomic_json_update(TASKS_FILE, modifier, [])
    save(load()); return 0

def cmd_done(task_id, output, summary):
    def modifier(tasks):
        t = find_task(tasks, task_id)
        if not t:
            return tasks
        output_value = str(output or '').strip()
        summary_text = str(summary or '').strip() or '任务已完成'
        blocker_report = detect_blocker_report({'output': output_value, 'summary': summary_text})
        if blocker_report:
            t['state'] = 'Blocked'
            t['org'] = '总裁办'
            t['block'] = blocker_report.get('summary') or summary_text
            t['now'] = blocker_report.get('summary') or summary_text
            source_meta = t.setdefault('sourceMeta', {})
            if not isinstance(source_meta, dict):
                source_meta = {}
                t['sourceMeta'] = source_meta
            source_meta['awaitingUserAction'] = bool(blocker_report.get('awaitingUserAction'))
            source_meta['blockerFeedback'] = blocker_report
            t['updatedAt'] = now_iso()
            _append_progress_snapshot(t, text=t['now'], todos=t.get('todos') or None)
            _mark_scheduler_progress(t)
            return tasks

        archived_output = _coerce_output_path(task_id, output_value, summary_text)
        t['state'] = 'Done'
        t['org'] = '完成'
        t['block'] = ''
        t['now'] = f'✅ {summary_text}'
        t['output'] = archived_output or output_value or summary_text
        if t.get('todos'):
            for item in t['todos']:
                if isinstance(item, dict) and item.get('status') != 'completed':
                    item['status'] = 'completed'
        t['updatedAt'] = now_iso()
        _append_progress_snapshot(t, text=t['now'], todos=t.get('todos') or None)
        _mark_scheduler_progress(t)
        return tasks
    atomic_json_update(TASKS_FILE, modifier, [])
    save(load()); return 0

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='更新任务看板状态')
    sub = parser.add_subparsers(dest='cmd', required=True)

    create = sub.add_parser('create')
    create.add_argument('task_id')
    create.add_argument('title')
    create.add_argument('state')
    create.add_argument('org')
    create.add_argument('official')

    state = sub.add_parser('state')
    state.add_argument('task_id')
    state.add_argument('new_state')
    state.add_argument('now_text', nargs='?')

    flow = sub.add_parser('flow')
    flow.add_argument('task_id')
    flow.add_argument('from_dept')
    flow.add_argument('to_dept')
    flow.add_argument('remark')

    progress = sub.add_parser('progress')
    progress.add_argument('task_id')
    progress.add_argument('now_text')
    progress.add_argument('plan_text')

    todo = sub.add_parser('todo')
    todo.add_argument('task_id')
    todo.add_argument('todo_id')
    todo.add_argument('title')
    todo.add_argument('status')
    todo.add_argument('--detail', default='')

    done = sub.add_parser('done')
    done.add_argument('task_id')
    done.add_argument('output')
    done.add_argument('summary')

    return parser

if __name__ == '__main__':
    ns = _build_parser().parse_args()
    if ns.cmd == 'create':
        raise SystemExit(cmd_create(ns.task_id, ns.title, ns.state, ns.org, ns.official))
    if ns.cmd == 'state':
        raise SystemExit(cmd_state(ns.task_id, ns.new_state, ns.now_text))
    if ns.cmd == 'flow':
        raise SystemExit(cmd_flow(ns.task_id, ns.from_dept, ns.to_dept, ns.remark))
    if ns.cmd == 'progress':
        raise SystemExit(cmd_progress(ns.task_id, ns.now_text, ns.plan_text))
    if ns.cmd == 'todo':
        raise SystemExit(cmd_todo(ns.task_id, ns.todo_id, ns.title, ns.status, ns.detail))
    if ns.cmd == 'done':
        raise SystemExit(cmd_done(ns.task_id, ns.output, ns.summary))
    raise SystemExit(1)

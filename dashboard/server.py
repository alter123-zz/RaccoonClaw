#!/usr/bin/env python3
"""
现代公司架构 · 看板本地 API 服务器
Port: 7891 (可通过 --port 修改)

Endpoints:
  GET  /                       → dashboard.html
  GET  /api/live-status        → data/live_status.json
  GET  /api/agent-config       → data/agent_config.json
  POST /api/set-model          → {agentId, model}
  GET  /api/model-change-log   → data/model_change_log.json
  GET  /api/last-result        → data/last_model_change_result.json
"""
import json, pathlib, subprocess, sys, threading, argparse, datetime, logging, re, os, io, inspect, importlib.util, zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from contextlib import redirect_stdout, redirect_stderr
from types import SimpleNamespace

# 引入文件锁工具，确保与其他脚本并发安全
scripts_dir = str(pathlib.Path(__file__).parent.parent / 'scripts')
sys.path.insert(0, scripts_dir)
from file_lock import atomic_json_read, atomic_json_write, atomic_json_update
from agent_registry import dashboard_agent_depts, org_agent_map, resolve_runtime_agent_id
from automation_health import build_automation_snapshot
from cron_jobs import CRON_JOBS_PATH, claim_due_jobs, finalize_job_run, reset_recurring_job_waiting, set_job_enabled, sync_jobs_from_tasks, upsert_job_for_task
from review_readiness import evaluate_review_readiness
from runtime_paths import canonical_data_dir, canonical_deliverables_root, openclaw_home
from task_ids import is_normal_task_id, next_task_id, normalize_flow_mode
from workbench_modes import default_target_dept_for_mode, inject_mode_id, resolve_mode_id_for_create
from workflow_registry import (
    workflow_manual_advance,
    workflow_org_resolved_states,
    workflow_state_agent_map,
    workflow_state_labels,
    workflow_terminal_states,
)
from utils import format_beijing, today_str, validate_url

log = logging.getLogger('server')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

OCLAW_HOME = openclaw_home()
MAX_REQUEST_BODY = 1 * 1024 * 1024  # 1 MB
ALLOWED_ORIGIN = None  # Set via --cors; None means restrict to localhost
_DEFAULT_ORIGINS = {
    'http://127.0.0.1:7891', 'http://localhost:7891',
    'http://127.0.0.1:5173', 'http://localhost:5173',  # Vite dev server
}
_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$')

BASE = pathlib.Path(__file__).parent
DIST = BASE / 'dist'          # React 构建产物 (npm run build)
DATA = canonical_data_dir()
SCRIPTS = BASE.parent / 'scripts'
DELIVERABLES_ROOT = canonical_deliverables_root()

# 静态资源 MIME 类型
_MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.svg':  'image/svg+xml',
    '.ico':  'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.ttf':  'font/ttf',
    '.map':  'application/json',
}

_LIVE_STATUS_REFRESH_LOCK = threading.Lock()
_TEXT_ATTACHMENT_EXTENSIONS = {
    '.txt', '.md', '.markdown', '.json', '.csv', '.tsv', '.log', '.py', '.js', '.ts', '.tsx',
    '.jsx', '.css', '.html', '.htm', '.xml', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.sh',
    '.zsh', '.bash', '.sql',
}
_TEXTUTIL_EXTENSIONS = {'.doc', '.docx', '.rtf', '.rtfd', '.odt', '.html', '.htm', '.webarchive'}


def _desktop_mode_enabled():
    return os.environ.get("OPENCLAW_APP_MODE", "").strip().lower() == "desktop"


def _completed_process(ok, stdout='', stderr='', code=0):
    return SimpleNamespace(
        returncode=0 if ok else (code if isinstance(code, int) else 1),
        stdout=stdout or '',
        stderr=stderr or '',
    )


def _run_embedded_script(module_name, argv=None):
    spec = importlib.util.spec_from_file_location(
        f"edictclaw_dashboard_{module_name}",
        SCRIPTS / f"{module_name}.py",
    )
    if spec is None or spec.loader is None:
        return {'ok': False, 'stdout': '', 'stderr': f'无法加载脚本: {module_name}', 'code': 1}

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        module = importlib.util.module_from_spec(spec)
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            spec.loader.exec_module(module)
            entry = getattr(module, 'main', None)
            if not callable(entry):
                raise RuntimeError(f'{module_name}.py 缺少 main()')
            if argv is None:
                result = entry()
            else:
                try:
                    result = entry(argv)
                except TypeError:
                    result = entry()
        code = 0 if result in (None, True) else int(result)
        return {
            'ok': code == 0,
            'stdout': stdout_buffer.getvalue().strip(),
            'stderr': stderr_buffer.getvalue().strip(),
            'code': code,
        }
    except Exception as exc:
        stderr = stderr_buffer.getvalue().strip()
        stderr = f'{stderr}\n{exc}'.strip() if stderr else str(exc)
        return {
            'ok': False,
            'stdout': stdout_buffer.getvalue().strip(),
            'stderr': stderr,
            'code': 1,
        }


def _run_maintenance_script(module_name, timeout=30):
    if _desktop_mode_enabled():
        result = _run_embedded_script(module_name)
        if not result.get('ok'):
            raise RuntimeError(result.get('stderr') or f'{module_name} 执行失败')
        return
    subprocess.run(['python3', str(SCRIPTS / f'{module_name}.py')], timeout=timeout)


def _run_delegate_agent(agent_id, message, timeout=300):
    agent_id = resolve_runtime_agent_id(agent_id)
    if _desktop_mode_enabled():
        result = _run_embedded_script(
            'delegate_agent',
            ['delegate_agent.py', agent_id, message, '--timeout', str(timeout)],
        )
        return _completed_process(
            result.get('ok', False),
            stdout=result.get('stdout', ''),
            stderr=result.get('stderr', ''),
            code=result.get('code', 1),
        )
    cmd = _delegate_agent_command(agent_id, message, timeout=timeout)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)


def read_json(path, default=None):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default if default is not None else {}


def _path_mtime(path):
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def _live_status_needs_refresh(path):
    if not path.exists():
        return True
    live_mtime = _path_mtime(path)
    dependency_names = (
        'tasks_source.json',
        'tasks.json',
        'officials_stats.json',
        'sync_status.json',
    )
    latest_input_mtime = max(_path_mtime(DATA / name) for name in dependency_names)
    return latest_input_mtime > live_mtime


def _ensure_live_status_fresh(path):
    if _live_status_needs_refresh(path):
        with _LIVE_STATUS_REFRESH_LOCK:
            if _live_status_needs_refresh(path):
                try:
                    _run_maintenance_script('refresh_live_data', timeout=30)
                except Exception as e:
                    log.warning(f'live_status 自动刷新失败: {e}')


def normalized_live_status_payload(path):
    _ensure_live_status_fresh(path)
    payload = read_json(path, {})
    tasks = payload.get('tasks')
    if isinstance(tasks, list):
        normalized_tasks = []
        for task in tasks:
            if not isinstance(task, dict):
                normalized_tasks.append(task)
                continue
            normalized_tasks.append(inject_mode_id(task))
        payload['tasks'] = normalized_tasks
    payload['automation'] = build_automation_snapshot()
    return payload


def cors_headers(h):
    req_origin = h.headers.get('Origin', '')
    if ALLOWED_ORIGIN:
        origin = ALLOWED_ORIGIN
    elif req_origin in _DEFAULT_ORIGINS:
        origin = req_origin
    else:
        origin = 'http://127.0.0.1:7891'
    h.send_header('Access-Control-Allow-Origin', origin)
    h.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    h.send_header('Access-Control-Allow-Headers', 'Content-Type')


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')


def _delegate_agent_command(agent_id, message, timeout=300):
    return [
        'python3',
        str(SCRIPTS / 'delegate_agent.py'),
        agent_id,
        message,
        '--timeout',
        str(timeout),
    ]


def _dispatch_error_text(result):
    stderr = (result.stderr or '').strip()
    stdout = (result.stdout or '').strip()
    parts = []
    if stderr:
        parts.append(stderr)
    if stdout and result.returncode != 0:
        parts.append(stdout)
    if not parts:
        return f'process exited with code {result.returncode}'
    return ' | '.join(parts)[:500]


def _dispatch_error_brief(raw: str, limit: int = 120) -> str:
    text = re.sub(r'\s+', ' ', str(raw or '').strip())
    if not text:
        return ''
    if len(text) <= limit:
        return text
    return text[:limit] + '…'


def _normalize_task_attachments(params):
    if not isinstance(params, dict):
        return []
    attachments = params.get('chatAttachments')
    if not isinstance(attachments, list):
        return []
    normalized = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        normalized.append({
            'id': str(item.get('id') or '').strip(),
            'name': str(item.get('name') or '').strip(),
            'path': str(item.get('path') or '').strip(),
            'kind': str(item.get('kind') or '').strip(),
            'contentType': str(item.get('contentType') or '').strip(),
            'uploadedAt': str(item.get('uploadedAt') or '').strip(),
            'textExcerpt': str(item.get('textExcerpt') or '').strip(),
        })
    return [item for item in normalized if item.get('name') or item.get('path')]


def _extract_attachment_excerpt(path_str, limit=6000):
    path = pathlib.Path(str(path_str or '').strip())
    if not path.exists() or not path.is_file():
        return ''
    ext = path.suffix.lower()
    def _finalize(raw):
        compact = re.sub(r'\n\s*\n+', '\n', str(raw or '')).strip()
        if len(compact) > limit:
            compact = compact[:limit] + '\n...[已截断]'
        return compact
    def _strip_xml(xml):
        raw = re.sub(r'</w:p>|</a:p>|</row>|</si>|</text:p>', '\n', xml)
        raw = re.sub(r'<[^>]+>', '', raw)
        return raw
    def _extract_zip_xml(*members):
        try:
            with zipfile.ZipFile(path) as archive:
                chunks = []
                for name in members:
                    if name.endswith('*'):
                        prefix = name[:-1]
                        matched = sorted(item for item in archive.namelist() if item.startswith(prefix))
                    else:
                        matched = [name] if name in archive.namelist() else []
                    for member in matched:
                        chunks.append(_strip_xml(archive.read(member).decode('utf-8', errors='ignore')))
        except Exception:
            return ''
        return _finalize('\n'.join(item for item in chunks if item))
    def _extract_textutil():
        if ext not in _TEXTUTIL_EXTENSIONS:
            return ''
        try:
            result = subprocess.run(
                ['/usr/bin/textutil', '-convert', 'txt', '-stdout', str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return ''
        if result.returncode != 0:
            return ''
        return _finalize(result.stdout)
    def _extract_mdls():
        try:
            result = subprocess.run(
                ['/usr/bin/mdls', '-raw', '-name', 'kMDItemTextContent', str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return ''
        if result.returncode != 0:
            return ''
        stdout = (result.stdout or '').strip()
        if not stdout or stdout == '(null)':
            return ''
        if stdout.startswith('"') and stdout.endswith('"'):
            stdout = stdout[1:-1]
        stdout = stdout.replace('\\n', '\n')
        return _finalize(stdout)
    def _extract_pdf_via_pdfkit():
        if ext != '.pdf':
            return ''
        escaped = str(path).replace('\\', '\\\\').replace('"', '\\"')
        script = (
            'import Foundation; import PDFKit; '
            f'let url = URL(fileURLWithPath: "{escaped}"); '
            'if let doc = PDFDocument(url: url) { print(doc.string ?? "") }'
        )
        env = os.environ.copy()
        env['CLANG_MODULE_CACHE_PATH'] = '/tmp/swift-module-cache'
        try:
            result = subprocess.run(
                ['/usr/bin/swift', '-e', script],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        except Exception:
            return ''
        if result.returncode != 0:
            return ''
        return _finalize(result.stdout)
    try:
        if ext == '.docx':
            compact = _extract_zip_xml('word/document.xml', 'word/header*.xml', 'word/footer*.xml')
        elif ext == '.xlsx':
            compact = _extract_zip_xml('xl/sharedStrings.xml', 'xl/worksheets/*')
        elif ext == '.pptx':
            compact = _extract_zip_xml('ppt/slides/*')
        elif ext in _TEXT_ATTACHMENT_EXTENSIONS:
            try:
                compact = path.read_text(encoding='utf-8').strip()
            except UnicodeDecodeError:
                compact = path.read_text(encoding='gb18030').strip()
        else:
            compact = _extract_textutil() or _extract_mdls() or _extract_pdf_via_pdfkit()
    except Exception:
        compact = ''
    if not compact:
        compact = _extract_textutil() or _extract_mdls() or _extract_pdf_via_pdfkit()
    return _finalize(compact)


def _task_attachment_summary_lines(task):
    params = task.get('templateParams') if isinstance(task.get('templateParams'), dict) else {}
    attachments = _normalize_task_attachments(params)
    if not attachments:
        return []
    lines = ['已附输入文档：']
    for item in attachments[:5]:
        label = item.get('name') or pathlib.Path(item.get('path') or '').name or '未命名文件'
        path = item.get('path') or ''
        lines.append(f'- {label}')
        if path:
            lines.append(f'  路径: {path}')
        excerpt = (item.get('textExcerpt') or '').strip()
        if not excerpt and path:
            excerpt = _extract_attachment_excerpt(path, limit=1200)
        if excerpt:
            lines.append(f'  摘录: {excerpt[:200]}')
    if len(attachments) > 5:
        lines.append(f'- 其余 {len(attachments) - 5} 个附件已省略')
    return lines


def _task_text_brief_lines(task):
    params = task.get('templateParams') if isinstance(task.get('templateParams'), dict) else {}
    source_meta = task.get('sourceMeta') if isinstance(task.get('sourceMeta'), dict) else {}
    brief = str(
        params.get('userBrief')
        or source_meta.get('userBrief')
        or params.get('rawRequest')
        or source_meta.get('rawRequest')
        or ''
    ).strip()
    if not brief:
        return []
    compact = re.sub(r'\n{3,}', '\n\n', brief).strip()
    if len(compact) > 1600:
        compact = compact[:1600].rstrip() + '\n...[已截断]'
    return ['需求方原话：', compact]


def load_tasks(data_root=None):
    base = pathlib.Path(data_root) if data_root is not None else DATA
    return atomic_json_read(base / 'tasks_source.json', [])


def save_tasks(tasks, data_root=None):
    base = pathlib.Path(data_root) if data_root is not None else DATA
    atomic_json_write(base / 'tasks_source.json', tasks)
    if data_root is not None:
        return
    # Trigger refresh (异步，不阻塞，避免僵尸进程)
    def _refresh():
        try:
            _run_maintenance_script('refresh_live_data', timeout=30)
        except Exception as e:
            log.warning(f'refresh_live_data.py 触发失败: {e}')
    threading.Thread(target=_refresh, daemon=True).start()


def _task_source_meta(task):
    source_meta = task.get('sourceMeta') or {}
    return source_meta if isinstance(source_meta, dict) else {}


def _scheduled_task_kind(task) -> str:
    source_meta = _task_source_meta(task)
    template_params = task.get('templateParams') or {}
    if not isinstance(template_params, dict):
        template_params = {}
    return str(source_meta.get('taskKind') or template_params.get('taskKind') or '').strip().lower()


def _scheduled_task_label(task, job=None) -> str:
    source_meta = _task_source_meta(task)
    if isinstance(job, dict):
        schedule = job.get('schedule') if isinstance(job.get('schedule'), dict) else {}
        label = str(schedule.get('label') or '').strip()
        if label:
            return label
    return str(source_meta.get('scheduleLabel') or task.get('output') or '定时任务').strip() or '定时任务'


def _scheduled_task_exec_org(task) -> str:
    source_meta = _task_source_meta(task)
    return (
        str(task.get('targetDept') or '').strip()
        or str(source_meta.get('dispatchOrg') or '').strip()
        or str(task.get('org') or '').strip()
        or '专项团队'
    )


def _sync_registered_scheduled_jobs():
    try:
        tasks = load_tasks()
        changed = False
        job_ids = []
        for task in tasks:
            if _scheduled_task_kind(task) not in {'oneshot', 'recurring'}:
                continue
            source_meta = task.setdefault('sourceMeta', {})
            if not isinstance(source_meta, dict):
                source_meta = {}
                task['sourceMeta'] = source_meta
            if str(task.get('state') or '') == 'Cancelled' or source_meta.get('jobEnabled') is False:
                continue
            job_id = upsert_job_for_task(task)
            job_ids.append(job_id)
            if str(source_meta.get('automationJobId') or '').strip() != job_id:
                source_meta['automationJobId'] = job_id
                changed = True
            if source_meta.get('jobEnabled') is not True:
                source_meta['jobEnabled'] = True
                changed = True
        if changed:
            save_tasks(tasks)
        return job_ids
    except Exception as exc:
        log.warning(f'⚠️ 同步定时任务到 cron 注册表失败: {exc}')
        return []


def _reconcile_recurring_waiting_tasks():
    tasks = load_tasks()
    try:
        jobs_by_id = {
            str(job.get('id') or ''): job
            for job in atomic_json_read(CRON_JOBS_PATH, {}).get('jobs', [])
            if isinstance(job, dict)
        }
    except Exception:
        jobs_by_id = {}

    changed = False
    for task in tasks:
        if _scheduled_task_kind(task) != 'recurring':
            continue
        if task.get('archived'):
            continue
        if not is_normal_task_id(str(task.get('id') or '')):
            continue
        if str(task.get('state') or '') not in _TERMINAL_STATES:
            continue
        source_meta = _task_source_meta(task)
        job_id = str(source_meta.get('automationJobId') or '').strip()
        job = jobs_by_id.get(job_id)
        if isinstance(job, dict) and not job.get('enabled', True):
            continue
        schedule_label = _scheduled_task_label(task, job)
        if job_id:
            reset_recurring_job_waiting(job_id)
        task['state'] = 'Assigned'
        task['org'] = '调度器'
        task['now'] = f'等待调度执行：{schedule_label}'
        task['block'] = '无'
        task['archived'] = False
        task.setdefault('flow_log', []).append({
            'at': now_iso(),
            'from': '结果回传',
            'to': '调度器',
            'remark': f'本轮执行已归档，返回调度器等待下一次执行：{schedule_label}',
        })
        _scheduler_mark_progress(task, f'周期任务回到等待态 {schedule_label}')
        task['updatedAt'] = now_iso()
        changed = True

    if changed:
        save_tasks(tasks)
    return changed


def _trigger_scheduled_task(job):
    task_id = str(job.get('taskId') or '').strip()
    if not task_id:
        return {'ok': False, 'status': 'error', 'error': 'job missing taskId'}
    tasks = load_tasks()
    task = next((item for item in tasks if str(item.get('id') or '') == task_id), None)
    if not task:
        return {'ok': False, 'status': 'error', 'error': f'task {task_id} not found'}

    task_kind = _scheduled_task_kind(task)
    if task_kind not in {'oneshot', 'recurring'}:
        return {'ok': False, 'status': 'error', 'error': f'task {task_id} is not scheduled'}

    state = str(task.get('state') or '').strip()
    if state not in _TERMINAL_STATES and str(task.get('org') or '').strip() != '调度器':
        return {'ok': False, 'status': 'skipped', 'error': f'task {task_id} still running in state {state}'}

    schedule_label = _scheduled_task_label(task, job)
    source_meta = _task_source_meta(task)
    flow_mode = str(source_meta.get('flowMode') or '').strip().lower()
    if flow_mode == 'full':
        next_state = 'ChiefOfStaff'
        next_org = '总裁办'
        now_text = f'⏰ 调度触发：{schedule_label}，交由总裁办推进完整链路'
        remark = f'定时触发 full 流程：{schedule_label}'
    else:
        next_state = 'Doing'
        next_org = _scheduled_task_exec_org(task)
        now_text = f'⏰ 调度触发执行：{schedule_label}'
        remark = f'定时触发执行：{schedule_label}'

    task['state'] = next_state
    task['org'] = next_org
    task['now'] = now_text
    task['block'] = '无'
    task['archived'] = False
    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '调度器',
        'to': next_org,
        'remark': remark,
    })
    _scheduler_mark_progress(task, f'调度触发 {schedule_label}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    dispatch_for_state(task_id, task, next_state, trigger='cron-due')
    return {'ok': True, 'status': 'queued', 'summary': now_text}


def handle_run_due_scheduled_jobs():
    _sync_registered_scheduled_jobs()
    _reconcile_recurring_waiting_tasks()
    claimed = claim_due_jobs()
    actions = []
    for job in claimed:
        job_id = str(job.get('id') or '').strip()
        task_id = str(job.get('taskId') or '').strip()
        result = _trigger_scheduled_task(job)
        status = str(result.get('status') or ('queued' if result.get('ok') else 'error'))
        error = str(result.get('error') or '')
        summary = str(result.get('summary') or '')
        finalize_job_run(
            job_id,
            status=status,
            delivery_status='queued' if status == 'queued' else status,
            summary=summary,
            error=error,
        )
        actions.append({
            'jobId': job_id,
            'taskId': task_id,
            'status': status,
            'message': summary or error or '已处理',
        })
    return {
        'ok': True,
        'count': len(actions),
        'actions': actions,
        'checkedAt': now_iso(),
    }


def handle_task_action(task_id, action, reason):
    """Stop/cancel/resume a task from the dashboard."""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}

    old_state = task.get('state', '')
    scheduled_task = _scheduled_task_kind(task) in {'oneshot', 'recurring'}
    source_meta = task.setdefault('sourceMeta', {})
    if not isinstance(source_meta, dict):
        source_meta = {}
        task['sourceMeta'] = source_meta
    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'task-action-before-{action}')

    if action == 'stop':
        task['state'] = 'Blocked'
        task['block'] = reason or '需求方叫停'
        task['now'] = f'⏸️ 已暂停：{reason}'
    elif action == 'cancel':
        task['state'] = 'Cancelled'
        task['block'] = reason or '需求方取消'
        task['now'] = f'🚫 已取消：{reason}'
        if scheduled_task:
            job_id = str(source_meta.get('automationJobId') or '').strip() or f'task-{task_id}'
            if job_id:
                set_job_enabled(job_id, False)
                source_meta['automationJobId'] = job_id
            source_meta['jobEnabled'] = False
    elif action == 'resume':
        # Resume to previous active state or Doing
        task['state'] = task.get('_prev_state', 'Doing')
        task['block'] = '无'
        task['now'] = f'▶️ 已恢复执行'

    if action in ('stop', 'cancel'):
        task['_prev_state'] = old_state  # Save for resume

    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '需求方',
        'to': task.get('org', ''),
        'remark': f'{"⏸️ 叫停" if action == "stop" else "🚫 取消" if action == "cancel" else "▶️ 恢复"}：{reason}'
    })

    if action == 'resume':
        _scheduler_mark_progress(task, f'恢复到 {task.get("state", "Doing")}')
    else:
        _scheduler_add_flow(task, f'需求方{action}：{reason or "无"}')

    task['updatedAt'] = now_iso()

    save_tasks(tasks)
    if action == 'resume' and task.get('state') not in _TERMINAL_STATES:
        dispatch_for_state(task_id, task, task.get('state'), trigger='resume')
    label = {'stop': '已叫停', 'cancel': '已取消', 'resume': '已恢复'}[action]
    return {'ok': True, 'message': f'{task_id} {label}'}


def handle_archive_task(task_id, archived, archive_all_done=False):
    """Archive or unarchive a task, or batch-archive all Done/Cancelled tasks."""
    tasks = load_tasks()
    if archive_all_done:
        count = 0
        for t in tasks:
            if t.get('state') in _TERMINAL_STATES and not t.get('archived'):
                t['archived'] = True
                t['archivedAt'] = now_iso()
                count += 1
        save_tasks(tasks)
        return {'ok': True, 'message': f'{count} 个任务已归档', 'count': count}
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    task['archived'] = archived
    if archived:
        task['archivedAt'] = now_iso()
    else:
        task.pop('archivedAt', None)
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    label = '已归档' if archived else '已取消归档'
    return {'ok': True, 'message': f'{task_id} {label}'}


def update_task_todos(task_id, todos):
    """Update the todos list for a task."""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}

    task['todos'] = todos
    task['updatedAt'] = now_iso()
    save_tasks(tasks)
    return {'ok': True, 'message': f'{task_id} todos 已更新'}


def read_skill_content(agent_id, skill_name):
    """Read SKILL.md content for a specific skill."""
    # 输入校验：防止路径遍历
    if not _SAFE_NAME_RE.match(agent_id) or not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': '参数含非法字符'}
    cfg = read_json(DATA / 'agent_config.json', {})
    agents = cfg.get('agents', [])
    ag = next((a for a in agents if a.get('id') == agent_id), None)
    if not ag:
        return {'ok': False, 'error': f'Agent {agent_id} 不存在'}
    sk = next((s for s in ag.get('skills', []) if s.get('name') == skill_name), None)
    if not sk:
        return {'ok': False, 'error': f'技能 {skill_name} 不存在'}
    skill_path = pathlib.Path(sk.get('path', '')).resolve()
    # 路径遍历保护：确保路径在 OCLAW_HOME 或项目目录下
    allowed_roots = (OCLAW_HOME.resolve(), BASE.parent.resolve())
    if not any(str(skill_path).startswith(str(root)) for root in allowed_roots):
        return {'ok': False, 'error': '路径不在允许的目录范围内'}
    if not skill_path.exists():
        return {'ok': True, 'name': skill_name, 'agent': agent_id, 'content': '(SKILL.md 文件不存在)', 'path': str(skill_path)}
    try:
        content = skill_path.read_text()
        return {'ok': True, 'name': skill_name, 'agent': agent_id, 'content': content, 'path': str(skill_path)}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def add_skill_to_agent(agent_id, skill_name, description, trigger=''):
    """Create a new skill for an agent with a standardised SKILL.md template."""
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skill_name 含非法字符: {skill_name}'}
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 含非法字符: {agent_id}'}
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    workspace.mkdir(parents=True, exist_ok=True)
    skill_md = workspace / 'SKILL.md'
    desc_line = description or skill_name
    trigger_section = f'\n## 触发条件\n{trigger}\n' if trigger else ''
    template = (f'---\n'
                f'name: {skill_name}\n'
                f'description: {desc_line}\n'
                f'---\n\n'
                f'# {skill_name}\n\n'
                f'{desc_line}\n'
                f'{trigger_section}\n'
                f'## 输入\n\n'
                f'<!-- 说明此技能接收什么输入 -->\n\n'
                f'## 处理流程\n\n'
                f'1. 步骤一\n'
                f'2. 步骤二\n\n'
                f'## 输出规范\n\n'
                f'<!-- 说明产出物格式与交付要求 -->\n\n'
                f'## 注意事项\n\n'
                f'- (在此补充约束、限制或特殊规则)\n')
    skill_md.write_text(template)
    # Re-sync agent config
    try:
        threading.Thread(target=_run_maintenance_script, args=('sync_agent_config',), daemon=True).start()
    except Exception:
        pass
    return {'ok': True, 'message': f'技能 {skill_name} 已添加到 {agent_id}', 'path': str(skill_md)}


def add_remote_skill(agent_id, skill_name, source_url, description=''):
    """从远程 URL 或本地路径为 Agent 添加 skill SKILL.md 文件。
    
    支持的源：
    - HTTPS URLs: https://raw.githubusercontent.com/...
    - 本地路径: /path/to/SKILL.md 或 file:///path/to/SKILL.md
    """
    # 输入校验
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 含非法字符: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 含非法字符: {skill_name}'}
    if not source_url or not isinstance(source_url, str):
        return {'ok': False, 'error': 'sourceUrl 必须是有效的字符串'}
    
    source_url = source_url.strip()
    
    # 检查 Agent 是否存在
    cfg = read_json(DATA / 'agent_config.json', {})
    agents = cfg.get('agents', [])
    if not any(a.get('id') == agent_id for a in agents):
        return {'ok': False, 'error': f'Agent {agent_id} 不存在'}
    
    # 下载或读取文件内容
    try:
        if source_url.startswith('http://') or source_url.startswith('https://'):
            # HTTPS URL 校验
            if not validate_url(source_url, allowed_schemes=('https',)):
                return {'ok': False, 'error': 'URL 无效或不安全（仅支持 HTTPS）'}
            
            # 从 URL 下载，带超时保护
            req = Request(source_url, headers={'User-Agent': 'OpenClaw-SkillManager/1.0'})
            try:
                resp = urlopen(req, timeout=10)
                content = resp.read(10 * 1024 * 1024).decode('utf-8')  # 最多 10MB
                if len(content) > 10 * 1024 * 1024:
                    return {'ok': False, 'error': '文件过大（最大 10MB）'}
            except Exception as e:
                return {'ok': False, 'error': f'URL 无法访问: {str(e)[:100]}'}
        
        elif source_url.startswith('file://'):
            # file:// URL 格式
            local_path = pathlib.Path(source_url[7:])
            if not local_path.exists():
                return {'ok': False, 'error': f'本地文件不存在: {local_path}'}
            content = local_path.read_text()
        
        elif source_url.startswith('/') or source_url.startswith('.'):
            # 本地绝对或相对路径
            local_path = pathlib.Path(source_url).resolve()
            if not local_path.exists():
                return {'ok': False, 'error': f'本地文件不存在: {local_path}'}
            # 路径遍历防护
            allowed_roots = (OCLAW_HOME.resolve(), BASE.parent.resolve())
            if not any(str(local_path).startswith(str(root)) for root in allowed_roots):
                return {'ok': False, 'error': '路径不在允许的目录范围内'}
            content = local_path.read_text()
        
        else:
            return {'ok': False, 'error': '不支持的 URL 格式（仅支持 https://, file://, 或本地路径）'}
    except Exception as e:
        return {'ok': False, 'error': f'文件读取失败: {str(e)[:100]}'}
    
    # 基础验证：检查是否为 Markdown 且包含 YAML frontmatter
    if not content.startswith('---'):
        return {'ok': False, 'error': '文件格式无效（缺少 YAML frontmatter）'}
    
    # 尝试解析 frontmatter
    try:
        import yaml
        parts = content.split('---', 2)
        if len(parts) < 3:
            return {'ok': False, 'error': '文件格式无效（YAML frontmatter 结构错误）'}
        frontmatter_str = parts[1]
        yaml.safe_load(frontmatter_str)  # 验证 YAML 格式
    except Exception as e:
        # 不要求完全的 YAML 解析，但要检查基本结构
        if 'name:' not in content[:500]:
            return {'ok': False, 'error': f'文件格式无效: {str(e)[:100]}'}
    
    # 创建本地目录
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    workspace.mkdir(parents=True, exist_ok=True)
    skill_md = workspace / 'SKILL.md'
    
    # 写入 SKILL.md
    skill_md.write_text(content)
    
    # 保存源信息到 .source.json
    source_info = {
        'skillName': skill_name,
        'sourceUrl': source_url,
        'description': description,
        'addedAt': now_iso(),
        'lastUpdated': now_iso(),
        'checksum': _compute_checksum(content),
        'status': 'valid',
    }
    source_json = workspace / '.source.json'
    source_json.write_text(json.dumps(source_info, ensure_ascii=False, indent=2))
    
    # Re-sync agent config
    try:
        threading.Thread(target=_run_maintenance_script, args=('sync_agent_config',), daemon=True).start()
    except Exception:
        pass
    
    return {
        'ok': True,
        'message': f'技能 {skill_name} 已从远程源添加到 {agent_id}',
        'skillName': skill_name,
        'agentId': agent_id,
        'source': source_url,
        'localPath': str(skill_md),
        'size': len(content),
        'addedAt': now_iso(),
    }


def get_remote_skills_list():
    """列表所有已添加的远程 skills 及其源信息"""
    remote_skills = []
    
    # 遍历所有 workspace
    for ws_dir in OCLAW_HOME.glob('workspace-*'):
        agent_id = ws_dir.name.replace('workspace-', '')
        skills_dir = ws_dir / 'skills'
        if not skills_dir.exists():
            continue
        
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            source_json = skill_dir / '.source.json'
            skill_md = skill_dir / 'SKILL.md'
            
            if not source_json.exists():
                # 本地创建的 skill，跳过
                continue
            
            try:
                source_info = json.loads(source_json.read_text())
                # 检查 SKILL.md 是否存在
                status = 'valid' if skill_md.exists() else 'not-found'
                remote_skills.append({
                    'skillName': skill_name,
                    'agentId': agent_id,
                    'sourceUrl': source_info.get('sourceUrl', ''),
                    'description': source_info.get('description', ''),
                    'localPath': str(skill_md),
                    'addedAt': source_info.get('addedAt', ''),
                    'lastUpdated': source_info.get('lastUpdated', ''),
                    'status': status,
                })
            except Exception:
                pass
    
    return {
        'ok': True,
        'remoteSkills': remote_skills,
        'count': len(remote_skills),
        'listedAt': now_iso(),
    }


def get_available_skills_catalog():
    """列出 OpenClaw 当前已有的可复用技能。"""
    catalog = {}
    builtin_skills_root = BASE.parent / 'skills'

    def skill_is_allowed(skill_dir, skill_md, content=''):
        if 'qclaw' in skill_dir.name.lower():
            return False
        return 'qclaw' not in (content or '').lower()

    def register_skill(skill_dir, source):
        skill_md = skill_dir / 'SKILL.md'
        if not skill_md.exists():
            return
        skill_name = skill_dir.name
        if not _SAFE_NAME_RE.match(skill_name):
            return

        description = ''
        content = ''
        try:
            content = skill_md.read_text(encoding='utf-8', errors='ignore')
            if not skill_is_allowed(skill_dir, skill_md, content):
                return
            parts = content.split('---', 2)
            if len(parts) >= 3:
                try:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    description = str(frontmatter.get('description') or '').strip()
                except Exception:
                    pass
        except Exception:
            pass
        if not skill_is_allowed(skill_dir, skill_md, content):
            return

        entry = catalog.setdefault(skill_name, {
            'name': skill_name,
            'description': description,
            'path': str(skill_md),
            'sources': set(),
            'agents': set(),
        })
        if description and not entry['description']:
            entry['description'] = description
        entry['sources'].add(source)

    # 全局技能目录
    for root in (
        OCLAW_HOME / 'skills',
        OCLAW_HOME / 'workspace' / 'skills',
        OCLAW_HOME / 'workspace' / '.global_skills',
    ):
        if not root.exists():
            continue
        for skill_dir in root.iterdir():
            if skill_dir.is_dir():
                register_skill(skill_dir, 'global')

    # OSS 仓库内置技能目录
    if builtin_skills_root.exists():
        for skill_dir in builtin_skills_root.iterdir():
            if skill_dir.is_dir():
                register_skill(skill_dir, 'builtin')

    # 各 Agent workspace 下已存在技能
    for ws_dir in OCLAW_HOME.glob('workspace-*'):
        agent_id = ws_dir.name.replace('workspace-', '')
        skills_dir = ws_dir / 'skills'
        if not skills_dir.exists():
            continue
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            register_skill(skill_dir, 'agent')
            catalog[skill_dir.name]['agents'].add(agent_id)

    skills = sorted(
        (
            {
                'name': item['name'],
                'description': item['description'],
                'path': item['path'],
                'sources': sorted(item['sources']),
                'agents': sorted(item['agents']),
            }
            for item in catalog.values()
        ),
        key=lambda x: x['name'],
    )
    return {
        'ok': True,
        'skills': skills,
        'count': len(skills),
        'listedAt': now_iso(),
    }


def update_remote_skill(agent_id, skill_name):
    """更新已添加的远程 skill 为最新版本（重新从源 URL 下载）"""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 含非法字符: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 含非法字符: {skill_name}'}
    
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    source_json = workspace / '.source.json'
    skill_md = workspace / 'SKILL.md'
    
    if not source_json.exists():
        return {'ok': False, 'error': f'技能 {skill_name} 不是远程 skill（无 .source.json）'}
    
    try:
        source_info = json.loads(source_json.read_text())
        source_url = source_info.get('sourceUrl', '')
        if not source_url:
            return {'ok': False, 'error': '源 URL 不存在'}
        
        # 重新下载
        result = add_remote_skill(agent_id, skill_name, source_url, 
                                  source_info.get('description', ''))
        if result['ok']:
            result['message'] = f'技能已更新'
            source_info_updated = json.loads(source_json.read_text())
            result['newVersion'] = source_info_updated.get('checksum', 'unknown')
        return result
    except Exception as e:
        return {'ok': False, 'error': f'更新失败: {str(e)[:100]}'}


def remove_remote_skill(agent_id, skill_name):
    """移除已添加的远程 skill"""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agentId 含非法字符: {agent_id}'}
    if not _SAFE_NAME_RE.match(skill_name):
        return {'ok': False, 'error': f'skillName 含非法字符: {skill_name}'}
    
    workspace = OCLAW_HOME / f'workspace-{agent_id}' / 'skills' / skill_name
    if not workspace.exists():
        return {'ok': False, 'error': f'技能不存在: {skill_name}'}
    
    # 检查是否为远程 skill
    source_json = workspace / '.source.json'
    if not source_json.exists():
        return {'ok': False, 'error': f'技能 {skill_name} 不是远程 skill，无法通过此 API 移除'}
    
    try:
        # 删除整个 skill 目录
        import shutil
        shutil.rmtree(workspace)
        
        # Re-sync agent config
        try:
            threading.Thread(target=_run_maintenance_script, args=('sync_agent_config',), daemon=True).start()
        except Exception:
            pass
        
        return {'ok': True, 'message': f'技能 {skill_name} 已从 {agent_id} 移除'}
    except Exception as e:
        return {'ok': False, 'error': f'移除失败: {str(e)[:100]}'}


def _compute_checksum(content: str) -> str:
    """计算内容的简单校验和（SHA256 的前16字符）"""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# 任务标题最低要求
_MIN_TITLE_LEN = 10
_JUNK_TITLES = {
    '?', '？', '好', '好的', '是', '否', '不', '不是', '对', '了解', '收到',
    '嗯', '哦', '知道了', '开启了么', '可以', '不行', '行', 'ok', 'yes', 'no',
    '你去开启', '测试', '试试', '看看',
}


def handle_create_task(title, org='产品规划部', official='产品规划负责人', priority='normal', template_id='', params=None, target_dept='', mode_id='', flow_mode='full'):
    """从看板创建新任务（任务模板发起）。"""
    if not title or not title.strip():
        return {'ok': False, 'error': '任务标题不能为空'}
    title = title.strip()
    # 剥离 Conversation info 元数据
    title = re.split(r'\n*Conversation info\s*\(', title, maxsplit=1)[0].strip()
    title = re.split(r'\n*```', title, maxsplit=1)[0].strip()
    # 清理常见前缀: "传旨:" "下旨:" "发起需求:" 等
    title = re.sub(r'^(传旨|下旨|发起需求)[：:\uff1a]\s*', '', title)
    if len(title) > 100:
        title = title[:100] + '…'
    # 标题质量校验：防止闲聊被误建为正式任务
    if len(title) < _MIN_TITLE_LEN:
        return {'ok': False, 'error': f'标题过短（{len(title)}<{_MIN_TITLE_LEN}字），不像是正式任务'}
    if title.lower() in _JUNK_TITLES:
        return {'ok': False, 'error': f'「{title}」不是有效任务，请输入具体工作指令'}
    params = params or {}
    flow_mode = normalize_flow_mode(flow_mode)
    task_kind = str(params.get('taskKind') or 'normal').strip().lower()
    is_scheduled_task = task_kind in {'oneshot', 'recurring'}
    schedule_label = str(params.get('scheduleLabel') or '').strip()
    scheduled_at = str(params.get('scheduledAt') or '').strip()
    tasks = load_tasks()
    existing_ids = {
        str(t.get('id') or '').strip()
        for t in tasks
        if is_normal_task_id(str(t.get('id') or '').strip())
    }
    try:
        existing_ids.update(
            path.name
            for path in DELIVERABLES_ROOT.iterdir()
            if path.is_dir()
            and is_normal_task_id(path.name)
        )
    except Exception:
        pass
    task_id = next_task_id(datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=8))), flow_mode, existing_ids)
    # 正确流程起点：需求方 -> 总裁办分诊
    # target_dept 记录模板建议的最终执行部门（仅供交付运营部派发参考）
    initial_org = '总裁办'
    resolved_mode_id = resolve_mode_id_for_create(mode_id, template_id, target_dept, params)
    effective_target_dept = str(target_dept or '').strip()
    mode_default_target_dept = default_target_dept_for_mode(resolved_mode_id)
    if mode_default_target_dept and (
        not effective_target_dept
        or effective_target_dept in {'总裁办', '产品规划部', '评审质控部', '交付运营部'}
    ):
        effective_target_dept = mode_default_target_dept
    task_attachments = _normalize_task_attachments(params)
    new_task = {
        'id': task_id,
        'title': title,
        'official': official,
        'org': initial_org,
        'state': 'ChiefOfStaff',
        'now': '等待总裁办分诊',
        'eta': '-',
        'block': '无',
        'output': '',
        'ac': '',
        'priority': priority,
        'templateId': template_id,
        'templateParams': params,
        'flow_log': [{
            'at': now_iso(),
            'from': '需求方',
            'to': initial_org,
            'remark': f'发起任务：{title}'
        }],
        'updatedAt': now_iso(),
    }
    if effective_target_dept:
        new_task['targetDept'] = effective_target_dept
    source_meta = {}
    if resolved_mode_id:
        new_task['modeId'] = resolved_mode_id
        source_meta['modeId'] = resolved_mode_id
    if task_attachments:
        source_meta['chatAttachments'] = task_attachments
        source_meta['chatAttachmentCount'] = len(task_attachments)
        source_meta['hasChatAttachments'] = True
        names = '、'.join(item.get('name') or pathlib.Path(item.get('path') or '').name or '未命名文件' for item in task_attachments[:3])
        new_task['flow_log'][0]['remark'] = f"{new_task['flow_log'][0]['remark']}；已附输入文档：{names}"
        new_task['ac'] = f"输入附件：{names}"
    text_brief = str(params.get('userBrief') or params.get('rawRequest') or '').strip()
    if text_brief:
        source_meta['userBrief'] = text_brief
        source_meta['rawRequest'] = str(params.get('rawRequest') or '').strip()
        source_meta['hasUserBrief'] = True
        if not task_attachments:
            preview = re.sub(r'\s+', ' ', text_brief)[:60]
            new_task['flow_log'][0]['remark'] = f"{new_task['flow_log'][0]['remark']}；已附原始需求正文"
            if not new_task.get('ac'):
                new_task['ac'] = f"需求摘要：{preview}"
    source_meta = new_task.setdefault('sourceMeta', source_meta or {})
    source_meta['flowMode'] = flow_mode
    source_meta['flowProfile'] = flow_mode
    if task_kind in {'normal', 'oneshot', 'recurring'}:
        source_meta['taskKind'] = task_kind
    if schedule_label:
        source_meta['scheduleLabel'] = schedule_label
    if scheduled_at:
        source_meta['scheduledAt'] = scheduled_at
    for key in ('scheduleMode', 'scheduleTime', 'scheduleWeekday', 'scheduleMonthday'):
        value = str(params.get(key) or '').strip()
        if value:
            source_meta[key] = value

    route_mode = str(params.get('routeMode') or '').strip()
    if route_mode:
        source_meta['routeMode'] = route_mode
    flow_summary = str(params.get('flowSummary') or '').strip()
    if flow_summary:
        source_meta['flowSummary'] = flow_summary
    dispatch_agent = str(params.get('dispatchAgent') or '').strip()
    dispatch_org = str(params.get('dispatchOrg') or '').strip()
    if dispatch_agent:
        source_meta['dispatchAgent'] = dispatch_agent
    if dispatch_org:
        source_meta['dispatchOrg'] = dispatch_org
    required_stages = params.get('requiredStages')
    if isinstance(required_stages, list) and required_stages:
        source_meta['requiredStages'] = [str(item).strip() for item in required_stages if str(item).strip()]
    if 'skipPlanning' in params:
        source_meta['skipPlanning'] = bool(params.get('skipPlanning'))
    if 'skipReview' in params:
        source_meta['skipReview'] = bool(params.get('skipReview'))

    _ensure_scheduler(new_task)
    _scheduler_snapshot(new_task, 'create-task-initial')
    _scheduler_mark_progress(new_task, '任务创建')

    dispatch_state = 'ChiefOfStaff'
    dispatch_trigger = 'new-task'
    if is_scheduled_task:
        target_label = schedule_label or (scheduled_at.replace('T', ' ') if scheduled_at else '待补充调度规则')
        new_task['state'] = 'Assigned'
        new_task['org'] = '调度器'
        new_task['now'] = f'等待调度执行：{target_label}'
        new_task['block'] = '无'
        new_task['output'] = target_label
        new_task['flow_log'].append({
            'at': now_iso(),
            'from': '总裁办',
            'to': '调度器',
            'remark': f'已登记为{ "单次任务" if task_kind == "oneshot" else "定时任务" }，当前不立即派发执行'
        })
        _scheduler_mark_progress(new_task, f'登记调度任务 {target_label}')
        source_meta['automationJobId'] = upsert_job_for_task(new_task)
        dispatch_state = 'Assigned'
        dispatch_trigger = 'scheduled-create'
    elif flow_mode == 'direct':
        exec_org = effective_target_dept or '总裁办'
        new_task['state'] = 'Doing'
        new_task['org'] = exec_org
        new_task['now'] = f'总裁办按直办流程处理，当前由{exec_org}执行'
        new_task['flow_log'].append({
            'at': now_iso(),
            'from': '总裁办',
            'to': exec_org,
            'remark': '总裁办直办：不进入产品规划部与评审质控部'
        })
        _scheduler_mark_progress(new_task, f'总裁办直办 {exec_org}')
        dispatch_state = 'Doing'
        dispatch_trigger = 'direct-create'
    elif flow_mode == 'light':
        exec_org = effective_target_dept or '专项团队'
        new_task['state'] = 'Doing'
        new_task['org'] = exec_org
        new_task['now'] = f'总裁办已轻流程直派至{exec_org}执行'
        new_task['flow_log'].append({
            'at': now_iso(),
            'from': '总裁办',
            'to': exec_org,
            'remark': '轻流程直派：跳过产品规划部与评审质控部'
        })
        _scheduler_mark_progress(new_task, f'总裁办轻流程直派 {exec_org}')
        dispatch_state = 'Doing'
        dispatch_trigger = 'light-create'

    tasks.insert(0, new_task)
    save_tasks(tasks)
    log.info(f'创建任务: {task_id} | {title[:40]}')

    if not is_scheduled_task:
        dispatch_for_state(task_id, new_task, dispatch_state, trigger=dispatch_trigger)

    if is_scheduled_task:
        return {'ok': True, 'taskId': task_id, 'message': f'任务 {task_id} 已登记为调度任务，等待按计划执行'}
    if flow_mode == 'direct':
        return {'ok': True, 'taskId': task_id, 'message': f'任务 {task_id} 已创建，总裁办已按直办流程处理'}
    if flow_mode == 'light':
        return {'ok': True, 'taskId': task_id, 'message': f'任务 {task_id} 已创建，总裁办已轻流程直派至{new_task.get("org")}'}
    return {'ok': True, 'taskId': task_id, 'message': f'任务 {task_id} 已创建，正在派发给总裁办'}


def handle_review_action(task_id, action, comment=''):
    """评审质控部审批：通过/打回。"""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    current_state = _normalize_state_name(task.get('state', ''))
    if current_state not in ('Review', 'ReviewControl'):
        return {'ok': False, 'error': f'任务 {task_id} 当前状态为 {task.get("state")}，无法审批'}

    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'review-before-{action}')

    source_dept = '评审质控部' if current_state == 'ReviewControl' else '交付运营部'

    if action == 'approve':
        if current_state == 'ReviewControl':
            task['state'] = 'Assigned'
            task['now'] = '评审质控部已通过，移交交付运营部派发'
            remark = f'✅ 通过：{comment or "评审质控部审核通过"}'
            to_dept = '交付运营部'
        else:  # Review
            task['state'] = 'Done'
            task['now'] = '复核通过，任务完成'
            remark = f'✅ 复核通过：{comment or "审查通过"}'
            to_dept = '需求方'
    elif action == 'reject':
        round_num = (task.get('review_round') or 0) + 1
        task['review_round'] = round_num
        task['state'] = 'Planning'
        task['now'] = f'打回产品规划部修订（第{round_num}轮）'
        remark = f'🚫 打回：{comment or "需要修改"}'
        to_dept = '产品规划部'
    else:
        return {'ok': False, 'error': f'未知操作: {action}'}

    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': source_dept,
        'to': to_dept,
        'remark': remark
    })
    _scheduler_mark_progress(task, f'审议动作 {action} -> {task.get("state")}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    # 🚀 审批后自动派发对应 Agent
    new_state = task['state']
    if new_state not in _TERMINAL_STATES:
        dispatch_for_state(task_id, task, new_state)

    label = '已通过' if action == 'approve' else '已打回'
    dispatched = ' (已自动派发 Agent)' if new_state not in _TERMINAL_STATES else ''
    return {'ok': True, 'message': f'{task_id} {label}{dispatched}'}


# ══ Agent 在线状态检测 ══

_AGENT_DEPTS = dashboard_agent_depts()


def _check_gateway_alive():
    """检测 Gateway 进程是否在运行。"""
    try:
        result = subprocess.run(['pgrep', '-f', 'openclaw-gateway'],
                                capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def _check_gateway_probe():
    """通过 HTTP probe 检测 Gateway 是否响应。"""
    try:
        from urllib.request import urlopen
        resp = urlopen('http://127.0.0.1:18789/', timeout=3)
        return resp.status == 200
    except Exception:
        return False


def _get_agent_session_status(agent_id):
    """读取 Agent 的 sessions.json 获取活跃状态。
    返回: (last_active_ts_ms, session_count, is_busy)
    """
    sessions_file = OCLAW_HOME / 'agents' / agent_id / 'sessions' / 'sessions.json'
    if not sessions_file.exists():
        return 0, 0, False
    try:
        data = json.loads(sessions_file.read_text())
        if not isinstance(data, dict):
            return 0, 0, False
        session_count = len(data)
        last_ts = 0
        for v in data.values():
            ts = v.get('updatedAt', 0)
            if isinstance(ts, (int, float)) and ts > last_ts:
                last_ts = ts
        now_ms = int(datetime.datetime.now().timestamp() * 1000)
        age_ms = now_ms - last_ts if last_ts else 9999999999
        is_busy = age_ms <= 2 * 60 * 1000  # 2分钟内视为正在工作
        return last_ts, session_count, is_busy
    except Exception:
        return 0, 0, False


def _check_agent_process(agent_id):
    """检测是否有该 Agent 的 openclaw-agent 进程正在运行。"""
    try:
        result = subprocess.run(
            ['pgrep', '-f', f'openclaw.*--agent.*{agent_id}'],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_agent_workspace(agent_id):
    """检查 Agent 工作空间是否存在。"""
    ws = OCLAW_HOME / f'workspace-{agent_id}'
    return ws.is_dir()


def _get_agent_queue_counts():
    """统计每个 Agent 当前待处理的任务数。"""
    counts = {}
    org_map = org_agent_map()
    for task in load_tasks():
        if task.get('archived'):
            continue
        state = _normalize_state_name(str(task.get('state') or '').strip())
        if not state or state in workflow_terminal_states():
            continue
        agent_id = _STATE_AGENT_MAP.get(state)
        if not agent_id and state in workflow_org_resolved_states():
            agent_id = org_map.get(str(task.get('org') or '').strip())
        if not agent_id:
            continue
        counts[agent_id] = counts.get(agent_id, 0) + 1
    return counts


def get_agents_status():
    """获取所有 Agent 的在线状态。
    返回各 Agent 的:
    - status: 'running' | 'idle' | 'offline' | 'unconfigured'
    - lastActive: 最后活跃时间
    - sessions: 会话数
    - hasWorkspace: 工作空间是否存在
    - processAlive: 是否有进程在运行
    """
    gateway_alive = _check_gateway_alive()
    gateway_probe = _check_gateway_probe() if gateway_alive else False
    queue_counts = _get_agent_queue_counts()

    agents = []
    seen_ids = set()
    for dept in _AGENT_DEPTS:
        aid = dept['id']
        if aid in seen_ids:
            continue
        seen_ids.add(aid)

        has_workspace = _check_agent_workspace(aid)
        last_ts, sess_count, is_busy = _get_agent_session_status(aid)
        process_alive = _check_agent_process(aid)
        queued_tasks = queue_counts.get(aid, 0)

        # 状态判定
        if not has_workspace:
            status = 'unconfigured'
            status_label = '❌ 未配置'
        elif not gateway_alive:
            status = 'offline'
            status_label = '🔴 Gateway 离线'
        elif process_alive or is_busy:
            status = 'running'
            status_label = '🟢 运行中'
        elif queued_tasks > 0:
            status = 'queued'
            status_label = f'🟠 待处理 · {queued_tasks}项'
        elif last_ts > 0:
            now_ms = int(datetime.datetime.now().timestamp() * 1000)
            age_ms = now_ms - last_ts
            if age_ms <= 10 * 60 * 1000:  # 10分钟内
                status = 'idle'
                status_label = '🟡 待命'
            elif age_ms <= 3600 * 1000:  # 1小时内
                status = 'idle'
                status_label = '⚪ 空闲'
            else:
                status = 'idle'
                status_label = '⚪ 休眠'
        else:
            status = 'idle'
            status_label = '⚪ 无记录'

        # 格式化最后活跃时间
        last_active_str = None
        if last_ts > 0:
            try:
                last_active_str = format_beijing(last_ts, '%m-%d %H:%M')
            except Exception:
                pass

        agents.append({
            'id': aid,
            'label': dept['label'],
            'emoji': dept['emoji'],
            'role': dept['role'],
            'status': status,
            'statusLabel': status_label,
            'lastActive': last_active_str,
            'lastActiveTs': last_ts,
            'sessions': sess_count,
            'hasWorkspace': has_workspace,
            'processAlive': process_alive,
            'queuedTasks': queued_tasks,
        })

    return {
        'ok': True,
        'gateway': {
            'alive': gateway_alive,
            'probe': gateway_probe,
            'status': '🟢 运行中' if gateway_probe else ('🟡 进程在但无响应' if gateway_alive else '🔴 未启动'),
        },
        'agents': agents,
        'checkedAt': now_iso(),
    }


def wake_agent(agent_id, message=''):
    """唤醒指定 Agent，发送一条心跳/唤醒消息。"""
    if not _SAFE_NAME_RE.match(agent_id):
        return {'ok': False, 'error': f'agent_id 非法: {agent_id}'}
    if not _check_agent_workspace(agent_id):
        return {'ok': False, 'error': f'{agent_id} 工作空间不存在，请先配置'}
    if not _check_gateway_alive():
        return {'ok': False, 'error': 'Gateway 未启动，请先运行 openclaw gateway start'}

    # agent_id 直接作为 runtime_id（openclaw agents list 中的注册名）
    runtime_id = agent_id
    msg = message or f'🔔 系统心跳检测 — 请回复 OK 确认在线。当前时间: {now_iso()}'

    def do_wake():
        try:
            cmd = ['openclaw', 'agent', '--agent', runtime_id, '-m', msg, '--timeout', '120']
            log.info(f'🔔 唤醒 {agent_id}...')
            # 带重试（最多2次）
            for attempt in range(1, 3):
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=130)
                if result.returncode == 0:
                    log.info(f'✅ {agent_id} 已唤醒')
                    return
                err_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
                log.warning(f'⚠️ {agent_id} 唤醒失败(第{attempt}次): {err_msg}')
                if attempt < 2:
                    import time
                    time.sleep(5)
            log.error(f'❌ {agent_id} 唤醒最终失败')
        except subprocess.TimeoutExpired:
            log.error(f'❌ {agent_id} 唤醒超时(130s)')
        except Exception as e:
            log.warning(f'⚠️ {agent_id} 唤醒异常: {e}')
    threading.Thread(target=do_wake, daemon=True).start()

    return {'ok': True, 'message': f'{agent_id} 唤醒指令已发出，约10-30秒后生效'}


# ══ Agent 实时活动读取 ══

# 状态 → agent_id 映射
_STATE_AGENT_MAP = workflow_state_agent_map()
_ORG_AGENT_MAP = org_agent_map()
_ORG_RESOLVED_STATES = workflow_org_resolved_states()
_TERMINAL_STATES = workflow_terminal_states()
_LEGACY_STATE_ALIASES = {}
_SCHEDULER_COMPLETION_HINT_RE = re.compile(
    r'(已完成|完成排查|初步排查|排查完成|已提交|已产出|已给出|已返回|已发送|已同步|已处理)',
    re.IGNORECASE,
)


def _parse_iso(ts):
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except Exception:
        return None


def _normalize_state_name(state):
    if not isinstance(state, str):
        return ''
    state = state.strip()
    return _LEGACY_STATE_ALIASES.get(state, state)


def _ensure_scheduler(task):
    sched = task.setdefault('_scheduler', {})
    if not isinstance(sched, dict):
        sched = {}
        task['_scheduler'] = sched
    sched.setdefault('enabled', True)
    sched.setdefault('stallThresholdSec', 180)
    sched.setdefault('maxRetry', 1)
    sched.setdefault('retryCount', 0)
    sched.setdefault('escalationLevel', 0)
    sched.setdefault('autoRollback', True)
    if not sched.get('lastProgressAt'):
        sched['lastProgressAt'] = task.get('updatedAt') or now_iso()
    if 'stallSince' not in sched:
        sched['stallSince'] = None
    if 'lastDispatchStatus' not in sched:
        sched['lastDispatchStatus'] = 'idle'
    if 'snapshot' not in sched:
        sched['snapshot'] = {
            'state': task.get('state', ''),
            'org': task.get('org', ''),
            'now': task.get('now', ''),
            'savedAt': now_iso(),
            'note': 'init',
        }
    return sched


def _scheduler_add_flow(task, remark, to=''):
    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '总裁办调度',
        'to': to or task.get('org', ''),
        'remark': f'🧭 {remark}'
    })


def _scheduler_snapshot(task, note=''):
    sched = _ensure_scheduler(task)
    sched['snapshot'] = {
        'state': task.get('state', ''),
        'org': task.get('org', ''),
        'now': task.get('now', ''),
        'savedAt': now_iso(),
        'note': note or 'snapshot',
    }


def _scheduler_mark_progress(task, note=''):
    sched = _ensure_scheduler(task)
    sched['lastProgressAt'] = now_iso()
    sched['stallSince'] = None
    sched['retryCount'] = 0
    sched['escalationLevel'] = 0
    sched['lastEscalatedAt'] = None
    if note:
        _scheduler_add_flow(task, f'进展确认：{note}')


def _scheduler_force_block_reason(task, stalled_sec):
    now_text = str(task.get('now') or '')
    todo_titles = ' '.join(str(td.get('title') or '') for td in (task.get('todos') or []))
    if _SCHEDULER_COMPLETION_HINT_RE.search(f'{now_text} {todo_titles}'):
        return f'阶段性工作似乎已完成，但未继续收尾为 Done / Blocked / 回传（已停滞 {stalled_sec} 秒）'
    return f'任务已停滞 {stalled_sec} 秒，且未继续收尾为 Done / Blocked / 回传'


def _scheduler_force_block(task, reason, stalled_sec=0):
    sched = _ensure_scheduler(task)
    previous_org = str(task.get('org') or '')
    source_meta = task.setdefault('sourceMeta', {})
    if not isinstance(source_meta, dict):
        source_meta = {}
        task['sourceMeta'] = source_meta
    source_meta['awaitingUserAction'] = False
    source_meta['schedulerAutoBlocked'] = True
    source_meta['schedulerBlockedFromOrg'] = previous_org
    source_meta['blockerFeedback'] = {
        'taskId': task.get('id', ''),
        'state': 'Blocked',
        'org': '总裁办',
        'kind': 'workflow-closure',
        'summary': reason,
        'missingItems': ['需要执行方显式收尾：Done / Blocked / 回传'],
        'actions': [
            '如果任务其实已完成，请补齐交付物后标记 Done',
            '如果任务遇阻，请显式标记 Blocked 并说明原因',
            '如果只是阶段性结论，请继续回传到总裁办或推进下一步',
        ],
        'evidence': [
            f'当前状态仍为 {task.get("state", "") or "-"}',
            f'最后进展：{task.get("now", "") or "-"}',
            f'停滞时长：{stalled_sec} 秒',
        ],
    }
    task['state'] = 'Blocked'
    task['org'] = '总裁办'
    task['now'] = f'⛔ 总裁办调度兜底：{reason}'
    task['block'] = reason
    sched['retryCount'] = 0
    sched['escalationLevel'] = 0
    sched['stallSince'] = None
    sched['lastProgressAt'] = now_iso()
    sched['lastDispatchStatus'] = 'blocked'
    sched['lastDispatchError'] = reason[:200]
    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': '总裁办调度',
        'to': '总裁办',
        'remark': f'⛔ 自动转阻塞：{reason}',
    })
    task['updatedAt'] = now_iso()


def _update_task_scheduler(task_id, updater, data_root=None):
    tasks = load_tasks(data_root)
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return False
    sched = _ensure_scheduler(task)
    updater(task, sched)
    task['updatedAt'] = now_iso()
    save_tasks(tasks, data_root)
    return True


def get_scheduler_state(task_id):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    sched = _ensure_scheduler(task)
    last_progress = _parse_iso(sched.get('lastProgressAt') or task.get('updatedAt'))
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    stalled_sec = 0
    if last_progress:
        stalled_sec = max(0, int((now_dt - last_progress).total_seconds()))
    return {
        'ok': True,
        'taskId': task_id,
        'state': task.get('state', ''),
        'org': task.get('org', ''),
        'scheduler': sched,
        'stalledSec': stalled_sec,
        'checkedAt': now_iso(),
    }


def handle_scheduler_retry(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    state = task.get('state', '')
    if state in _TERMINAL_STATES or state == 'Blocked':
        return {'ok': False, 'error': f'任务 {task_id} 当前状态 {state} 不支持重试'}

    sched = _ensure_scheduler(task)
    sched['retryCount'] = int(sched.get('retryCount') or 0) + 1
    sched['lastRetryAt'] = now_iso()
    sched['lastDispatchTrigger'] = 'chief-of-staff-retry'
    _scheduler_add_flow(task, f'触发重试第{sched["retryCount"]}次：{reason or "超时未推进"}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    dispatch_for_state(task_id, task, state, trigger='chief-of-staff-retry')
    return {'ok': True, 'message': f'{task_id} 已触发重试派发', 'retryCount': sched['retryCount']}


def handle_scheduler_escalate(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    state = task.get('state', '')
    if state in _TERMINAL_STATES:
        return {'ok': False, 'error': f'任务 {task_id} 已结束，无需升级'}

    sched = _ensure_scheduler(task)
    current_level = int(sched.get('escalationLevel') or 0)
    next_level = min(current_level + 1, 2)
    target = 'review_control' if next_level == 1 else 'delivery_ops'
    target_label = '评审质控部' if next_level == 1 else '交付运营部'

    sched['escalationLevel'] = next_level
    sched['lastEscalatedAt'] = now_iso()
    _scheduler_add_flow(task, f'升级到{target_label}协调：{reason or "任务停滞"}', to=target_label)
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    msg = (
        f'🧭 总裁办调度升级通知\n'
        f'任务ID: {task_id}\n'
        f'当前状态: {state}\n'
        f'停滞处理: 请你介入协调推进\n'
        f'原因: {reason or "任务超过阈值未推进"}\n'
        f'⚠️ 看板已有任务，请勿重复创建。'
    )
    wake_agent(target, msg)

    return {'ok': True, 'message': f'{task_id} 已升级至{target_label}', 'escalationLevel': next_level}


def handle_scheduler_rollback(task_id, reason=''):
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    sched = _ensure_scheduler(task)
    snapshot = sched.get('snapshot') or {}
    snap_state = snapshot.get('state')
    if not snap_state:
        return {'ok': False, 'error': f'任务 {task_id} 无可用回滚快照'}

    old_state = task.get('state', '')
    task['state'] = snap_state
    task['org'] = snapshot.get('org', task.get('org', ''))
    task['now'] = f'↩️ 总裁办调度自动回滚：{reason or "恢复到上个稳定节点"}'
    task['block'] = '无'
    sched['retryCount'] = 0
    sched['escalationLevel'] = 0
    sched['stallSince'] = None
    sched['lastProgressAt'] = now_iso()
    _scheduler_add_flow(task, f'执行回滚：{old_state} → {snap_state}，原因：{reason or "停滞恢复"}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    if snap_state not in _TERMINAL_STATES:
        dispatch_for_state(task_id, task, snap_state, trigger='chief-of-staff-rollback')

    return {'ok': True, 'message': f'{task_id} 已回滚到 {snap_state}'}


def handle_scheduler_scan(threshold_sec=180):
    threshold_sec = max(30, int(threshold_sec or 180))
    tasks = load_tasks()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    pending_retries = []
    pending_escalates = []
    pending_rollbacks = []
    actions = []
    changed = False

    for task in tasks:
        task_id = task.get('id', '')
        state = task.get('state', '')
        if not task_id or state in _TERMINAL_STATES or task.get('archived'):
            continue
        if state == 'Blocked':
            continue
        source_meta = task.get('sourceMeta') or {}
        template_params = task.get('templateParams') or {}
        task_kind = str(source_meta.get('taskKind') or template_params.get('taskKind') or '').strip().lower()
        if task_kind in {'oneshot', 'recurring'}:
            continue

        sched = _ensure_scheduler(task)
        task_threshold = int(sched.get('stallThresholdSec') or threshold_sec)
        last_progress = _parse_iso(sched.get('lastProgressAt') or task.get('updatedAt'))
        if not last_progress:
            continue
        stalled_sec = max(0, int((now_dt - last_progress).total_seconds()))
        if stalled_sec < task_threshold:
            continue

        if not sched.get('stallSince'):
            sched['stallSince'] = now_iso()
            changed = True

        retry_count = int(sched.get('retryCount') or 0)
        max_retry = max(0, int(sched.get('maxRetry') or 1))
        level = int(sched.get('escalationLevel') or 0)

        if retry_count < max_retry:
            sched['retryCount'] = retry_count + 1
            sched['lastRetryAt'] = now_iso()
            sched['lastDispatchTrigger'] = 'chief-of-staff-scan-retry'
            _scheduler_add_flow(task, f'停滞{stalled_sec}秒，触发自动重试第{sched["retryCount"]}次')
            pending_retries.append((task_id, state))
            actions.append({'taskId': task_id, 'action': 'retry', 'stalledSec': stalled_sec})
            changed = True
            continue

        if level < 2:
            next_level = level + 1
            target = 'review_control' if next_level == 1 else 'delivery_ops'
            target_label = '评审质控部' if next_level == 1 else '交付运营部'
            sched['escalationLevel'] = next_level
            sched['lastEscalatedAt'] = now_iso()
            _scheduler_add_flow(task, f'停滞{stalled_sec}秒，升级至{target_label}协调', to=target_label)
            pending_escalates.append((task_id, state, target, target_label, stalled_sec))
            actions.append({'taskId': task_id, 'action': 'escalate', 'to': target_label, 'stalledSec': stalled_sec})
            changed = True
            continue

        if sched.get('autoRollback', True):
            snapshot = sched.get('snapshot') or {}
            snap_state = snapshot.get('state')
            if snap_state and snap_state != state:
                old_state = state
                task['state'] = snap_state
                task['org'] = snapshot.get('org', task.get('org', ''))
                task['now'] = '↩️ 总裁办调度自动回滚到稳定节点'
                task['block'] = '无'
                sched['retryCount'] = 0
                sched['escalationLevel'] = 0
                sched['stallSince'] = None
                sched['lastProgressAt'] = now_iso()
                _scheduler_add_flow(task, f'连续停滞，自动回滚：{old_state} → {snap_state}')
                pending_rollbacks.append((task_id, snap_state))
                actions.append({'taskId': task_id, 'action': 'rollback', 'toState': snap_state})
                changed = True
                continue

        reason = _scheduler_force_block_reason(task, stalled_sec)
        _scheduler_force_block(task, reason, stalled_sec)
        actions.append({'taskId': task_id, 'action': 'force-block', 'stalledSec': stalled_sec})
        changed = True

    if changed:
        save_tasks(tasks)

    for task_id, state in pending_retries:
        retry_task = next((t for t in tasks if t.get('id') == task_id), None)
        if retry_task:
            dispatch_for_state(task_id, retry_task, state, trigger='chief-of-staff-scan-retry')

    for task_id, state, target, target_label, stalled_sec in pending_escalates:
        msg = (
            f'🧭 总裁办调度升级通知\n'
            f'任务ID: {task_id}\n'
            f'当前状态: {state}\n'
            f'已停滞: {stalled_sec} 秒\n'
            f'请立即介入协调推进\n'
            f'⚠️ 看板已有任务，请勿重复创建。'
        )
        wake_agent(target, msg)

    for task_id, state in pending_rollbacks:
        rollback_task = next((t for t in tasks if t.get('id') == task_id), None)
        if rollback_task and state not in _TERMINAL_STATES:
            dispatch_for_state(task_id, rollback_task, state, trigger='chief-of-staff-auto-rollback')

    return {
        'ok': True,
        'thresholdSec': threshold_sec,
        'actions': actions,
        'count': len(actions),
        'checkedAt': now_iso(),
    }


def _startup_recover_queued_dispatches():
    """服务启动后扫描 lastDispatchStatus=queued 的任务，重新派发。
    解决：kill -9 重启导致派发线程中断、任务永久卡住的问题。"""
    tasks = load_tasks()
    recovered = 0
    for task in tasks:
        task_id = task.get('id', '')
        state = task.get('state', '')
        if not task_id or state in _TERMINAL_STATES or task.get('archived'):
            continue
        sched = task.get('_scheduler') or {}
        if sched.get('lastDispatchStatus') == 'queued':
            log.info(f'🔄 启动恢复: {task_id} 状态={state} 上次派发未完成，重新派发')
            sched['lastDispatchTrigger'] = 'startup-recovery'
            dispatch_for_state(task_id, task, state, trigger='startup-recovery')
            recovered += 1
    if recovered:
        log.info(f'✅ 启动恢复完成: 重新派发 {recovered} 个任务')
    else:
        log.info(f'✅ 启动恢复: 无需恢复')


def handle_repair_flow_order():
    """修复历史任务中首条流转为“需求方->产品规划部”的错序问题。"""
    tasks = load_tasks()
    fixed = 0
    fixed_ids = []

    for task in tasks:
        task_id = task.get('id', '')
        if not is_normal_task_id(task_id):
            continue
        flow_log = task.get('flow_log') or []
        if not flow_log:
            continue

        first = flow_log[0]
        if first.get('from') != '需求方' or first.get('to') != '产品规划部':
            continue

        first['to'] = '总裁办'
        remark = first.get('remark', '')
        if isinstance(remark, str) and remark.startswith('发起任务：'):
            first['remark'] = remark

        if task.get('state') == 'Planning' and task.get('org') == '产品规划部' and len(flow_log) == 1:
            task['state'] = 'ChiefOfStaff'
            task['org'] = '总裁办'
            task['now'] = '等待总裁办分诊'

        task['updatedAt'] = now_iso()
        fixed += 1
        fixed_ids.append(task_id)

    if fixed:
        save_tasks(tasks)

    return {
        'ok': True,
        'count': fixed,
        'taskIds': fixed_ids[:80],
        'more': max(0, fixed - 80),
        'checkedAt': now_iso(),
    }


def _collect_message_text(msg):
    """收集消息中的可检索文本，用于 task_id/关键词过滤。"""
    parts = []
    for c in msg.get('content', []) or []:
        ctype = c.get('type')
        if ctype == 'text' and c.get('text'):
            parts.append(str(c.get('text', '')))
        elif ctype == 'thinking' and c.get('thinking'):
            parts.append(str(c.get('thinking', '')))
        elif ctype == 'tool_use':
            parts.append(json.dumps(c.get('input', {}), ensure_ascii=False))
    details = msg.get('details') or {}
    for key in ('output', 'stdout', 'stderr', 'message'):
        val = details.get(key)
        if isinstance(val, str) and val:
            parts.append(val)
    return ''.join(parts)


def _parse_activity_entry(item):
    """将 session jsonl 的 message 统一解析成看板活动条目。"""
    msg = item.get('message') or {}
    role = str(msg.get('role', '')).strip().lower()
    ts = item.get('timestamp', '')

    if role == 'assistant':
        text = ''
        thinking = ''
        tool_calls = []
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text') and not text:
                text = str(c.get('text', '')).strip()
            elif c.get('type') == 'thinking' and c.get('thinking') and not thinking:
                thinking = str(c.get('thinking', '')).strip()[:200]
            elif c.get('type') == 'tool_use':
                tool_calls.append({
                    'name': c.get('name', ''),
                    'input_preview': json.dumps(c.get('input', {}), ensure_ascii=False)[:100]
                })
        if not (text or thinking or tool_calls):
            return None
        entry = {'at': ts, 'kind': 'assistant'}
        if text:
            entry['text'] = text[:300]
        if thinking:
            entry['thinking'] = thinking
        if tool_calls:
            entry['tools'] = tool_calls
        return entry

    if role in ('toolresult', 'tool_result'):
        details = msg.get('details') or {}
        code = details.get('exitCode')
        if code is None:
            code = details.get('code', details.get('status'))
        output = ''
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text'):
                output = str(c.get('text', '')).strip()[:200]
                break
        if not output:
            for key in ('output', 'stdout', 'stderr', 'message'):
                val = details.get(key)
                if isinstance(val, str) and val.strip():
                    output = val.strip()[:200]
                    break

        entry = {
            'at': ts,
            'kind': 'tool_result',
            'tool': msg.get('toolName', msg.get('name', '')),
            'exitCode': code,
            'output': output,
        }
        duration_ms = details.get('durationMs')
        if isinstance(duration_ms, (int, float)):
            entry['durationMs'] = int(duration_ms)
        return entry

    if role == 'user':
        text = ''
        for c in msg.get('content', []) or []:
            if c.get('type') == 'text' and c.get('text'):
                text = str(c.get('text', '')).strip()
                break
        if not text:
            return None
        return {'at': ts, 'kind': 'user', 'text': text[:200]}

    return None


def get_agent_activity(agent_id, limit=30, task_id=None):
    """从 Agent 的 session jsonl 读取最近活动。
    如果 task_id 不为空，只返回提及该 task_id 的相关条目。
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    # 扫描所有 jsonl（按修改时间倒序），优先最新
    jsonl_files = sorted(sessions_dir.glob('*.jsonl'), key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    entries = []
    # 如果需要按 task_id 过滤，可能需要扫描多个文件
    files_to_scan = jsonl_files[:3] if task_id else jsonl_files[:1]

    for session_file in files_to_scan:
        try:
            lines = session_file.read_text(errors='ignore').splitlines()
        except Exception:
            continue

        # 正向扫描以保持时间顺序；如果有 task_id，收集提及 task_id 的条目
        for ln in lines:
            try:
                item = json.loads(ln)
            except Exception:
                continue
            msg = item.get('message') or {}
            all_text = _collect_message_text(msg)

            # task_id 过滤：只保留提及 task_id 的条目
            if task_id and task_id not in all_text:
                continue
            entry = _parse_activity_entry(item)
            if entry:
                entries.append(entry)

            if len(entries) >= limit:
                break
        if len(entries) >= limit:
            break

    # 只保留最后 limit 条
    return entries[-limit:]


def _extract_keywords(title):
    """从任务标题中提取有意义的关键词（用于 session 内容匹配）。"""
    stop = {'的', '了', '在', '是', '有', '和', '与', '或', '一个', '一篇', '关于', '进行',
            '写', '做', '请', '把', '给', '用', '要', '需要', '面向', '风格', '包含',
            '出', '个', '不', '可以', '应该', '如何', '怎么', '什么', '这个', '那个'}
    # 提取英文词
    en_words = re.findall(r'[a-zA-Z][\w.-]{1,}', title)
    # 提取 2-4 字中文词组（更短的颗粒度）
    cn_words = re.findall(r'[\u4e00-\u9fff]{2,4}', title)
    all_words = en_words + cn_words
    kws = [w for w in all_words if w not in stop and len(w) >= 2]
    # 去重保序
    seen = set()
    unique = []
    for w in kws:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique.append(w)
    return unique[:8]  # 最多 8 个关键词


def get_agent_activity_by_keywords(agent_id, keywords, limit=20):
    """从 agent session 中按关键词匹配获取活动条目。
    找到包含关键词的 session 文件，只读该文件的活动。
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    jsonl_files = sorted(sessions_dir.glob('*.jsonl'), key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    # 找到包含关键词的 session 文件
    target_file = None
    for sf in jsonl_files[:5]:
        try:
            content = sf.read_text(errors='ignore')
        except Exception:
            continue
        hits = sum(1 for kw in keywords if kw.lower() in content.lower())
        if hits >= min(2, len(keywords)):
            target_file = sf
            break

    if not target_file:
        return []

    # 解析 session 文件，按 user 消息分割为对话段
    # 找到包含关键词的对话段，只返回该段的活动
    try:
        lines = target_file.read_text(errors='ignore').splitlines()
    except Exception:
        return []

    # 第一遍：找到关键词匹配的 user 消息位置
    user_msg_indices = []  # (line_index, user_text)
    for i, ln in enumerate(lines):
        try:
            item = json.loads(ln)
        except Exception:
            continue
        msg = item.get('message') or {}
        if msg.get('role') == 'user':
            text = ''
            for c in msg.get('content', []):
                if c.get('type') == 'text' and c.get('text'):
                    text += c['text']
            user_msg_indices.append((i, text))

    # 找到与关键词匹配度最高的 user 消息
    best_idx = -1
    best_hits = 0
    for line_idx, utext in user_msg_indices:
        hits = sum(1 for kw in keywords if kw.lower() in utext.lower())
        if hits > best_hits:
            best_hits = hits
            best_idx = line_idx

    # 确定对话段的行范围：从匹配的 user 消息到下一个 user 消息之前
    if best_idx >= 0 and best_hits >= min(2, len(keywords)):
        # 找下一个 user 消息的位置
        next_user_idx = len(lines)
        for line_idx, _ in user_msg_indices:
            if line_idx > best_idx:
                next_user_idx = line_idx
                break
        start_line = best_idx
        end_line = next_user_idx
    else:
        # 没找到匹配的对话段，返回空
        return []

    # 第二遍：只解析对话段内的行
    entries = []
    for ln in lines[start_line:end_line]:
        try:
            item = json.loads(ln)
        except Exception:
            continue
        entry = _parse_activity_entry(item)
        if entry:
            entries.append(entry)

    return entries[-limit:]


def get_agent_latest_segment(agent_id, limit=20):
    """获取 Agent 最新一轮对话段（最后一条 user 消息起的所有内容）。
    用于活跃任务没有精确匹配时，展示 Agent 的实时工作状态。
    """
    sessions_dir = OCLAW_HOME / 'agents' / agent_id / 'sessions'
    if not sessions_dir.exists():
        return []

    jsonl_files = sorted(sessions_dir.glob('*.jsonl'),
                         key=lambda f: f.stat().st_mtime, reverse=True)
    if not jsonl_files:
        return []

    # 读取最新的 session 文件
    target_file = jsonl_files[0]
    try:
        lines = target_file.read_text(errors='ignore').splitlines()
    except Exception:
        return []

    # 找到最后一条 user 消息的行号
    last_user_idx = -1
    for i, ln in enumerate(lines):
        try:
            item = json.loads(ln)
        except Exception:
            continue
        msg = item.get('message') or {}
        if msg.get('role') == 'user':
            last_user_idx = i

    if last_user_idx < 0:
        return []

    # 从最后一条 user 消息开始，解析到文件末尾
    entries = []
    for ln in lines[last_user_idx:]:
        try:
            item = json.loads(ln)
        except Exception:
            continue
        entry = _parse_activity_entry(item)
        if entry:
            entries.append(entry)

    return entries[-limit:]


def _compute_phase_durations(flow_log):
    """从 flow_log 计算每个阶段的停留时长。"""
    if not flow_log or len(flow_log) < 1:
        return []
    phases = []
    for i, fl in enumerate(flow_log):
        start_at = fl.get('at', '')
        to_dept = fl.get('to', '')
        remark = fl.get('remark', '')
        # 下一阶段的起始时间就是本阶段的结束时间
        if i + 1 < len(flow_log):
            end_at = flow_log[i + 1].get('at', '')
            ongoing = False
        else:
            end_at = now_iso()
            ongoing = True
        # 计算时长
        dur_sec = 0
        try:
            from_dt = datetime.datetime.fromisoformat(start_at.replace('Z', '+00:00'))
            to_dt = datetime.datetime.fromisoformat(end_at.replace('Z', '+00:00'))
            dur_sec = max(0, int((to_dt - from_dt).total_seconds()))
        except Exception:
            pass
        # 人类可读时长
        if dur_sec < 60:
            dur_text = f'{dur_sec}秒'
        elif dur_sec < 3600:
            dur_text = f'{dur_sec // 60}分{dur_sec % 60}秒'
        elif dur_sec < 86400:
            h, rem = divmod(dur_sec, 3600)
            dur_text = f'{h}小时{rem // 60}分'
        else:
            d, rem = divmod(dur_sec, 86400)
            dur_text = f'{d}天{rem // 3600}小时'
        phases.append({
            'phase': to_dept,
            'from': start_at,
            'to': end_at,
            'durationSec': dur_sec,
            'durationText': dur_text,
            'ongoing': ongoing,
            'remark': remark,
        })
    return phases


def _compute_todos_summary(todos):
    """计算 todos 完成率汇总。"""
    if not todos:
        return None
    total = len(todos)
    completed = sum(1 for t in todos if t.get('status') == 'completed')
    in_progress = sum(1 for t in todos if t.get('status') == 'in-progress')
    not_started = total - completed - in_progress
    percent = round(completed / total * 100) if total else 0
    return {
        'total': total,
        'completed': completed,
        'inProgress': in_progress,
        'notStarted': not_started,
        'percent': percent,
    }


def _compute_todos_diff(prev_todos, curr_todos):
    """计算两个 todos 快照之间的差异。"""
    prev_map = {str(t.get('id', '')): t for t in (prev_todos or [])}
    curr_map = {str(t.get('id', '')): t for t in (curr_todos or [])}
    changed, added, removed = [], [], []
    for tid, ct in curr_map.items():
        if tid in prev_map:
            pt = prev_map[tid]
            if pt.get('status') != ct.get('status'):
                changed.append({
                    'id': tid, 'title': ct.get('title', ''),
                    'from': pt.get('status', ''), 'to': ct.get('status', ''),
                })
        else:
            added.append({'id': tid, 'title': ct.get('title', '')})
    for tid, pt in prev_map.items():
        if tid not in curr_map:
            removed.append({'id': tid, 'title': pt.get('title', '')})
    if not changed and not added and not removed:
        return None
    return {'changed': changed, 'added': added, 'removed': removed}


def get_task_activity(task_id):
    """获取任务的实时进展数据。
    数据来源：
    1. 任务自身的 now / todos / flow_log 字段（由 Agent 通过 progress 命令主动上报）
    2. Agent session JSONL 中的对话日志（thinking / tool_result / user，用于展示思考过程）

    增强字段:
    - taskMeta: 任务元信息 (title/state/org/output/block/priority/reviewRound/archived)
    - phaseDurations: 各阶段停留时长
    - todosSummary: todos 完成率汇总
    - resourceSummary: Agent 资源消耗汇总 (tokens/cost/elapsed)
    - activity 条目中 progress/todos 保留 state/org 快照
    - activity 中 todos 条目含 diff 字段
    """
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}

    state = task.get('state', '')
    org = task.get('org', '')
    now_text = task.get('now', '')
    todos = task.get('todos', [])
    updated_at = task.get('updatedAt', '')

    # ── 任务元信息 ──
    task_meta = {
        'title': task.get('title', ''),
        'state': state,
        'org': org,
        'output': task.get('output', ''),
        'block': task.get('block', ''),
        'priority': task.get('priority', 'normal'),
        'reviewRound': task.get('review_round', 0),
        'archived': task.get('archived', False),
    }

    # 当前负责 Agent（兼容旧逻辑）
    agent_id = _STATE_AGENT_MAP.get(state)
    if agent_id is None and state in _ORG_RESOLVED_STATES:
        agent_id = _ORG_AGENT_MAP.get(org)

    # ── 构建活动条目列表（flow_log + progress_log）──
    activity = []
    flow_log = task.get('flow_log', [])

    # 1. flow_log 转为活动条目
    for fl in flow_log:
        activity.append({
            'at': fl.get('at', ''),
            'kind': 'flow',
            'from': fl.get('from', ''),
            'to': fl.get('to', ''),
            'remark': fl.get('remark', ''),
        })

    progress_log = task.get('progress_log', [])
    related_agents = set()

    # 资源消耗累加
    total_tokens = 0
    total_cost = 0.0
    total_elapsed = 0
    has_resource_data = False

    # 用于 todos diff 计算
    prev_todos_snapshot = None

    if progress_log:
        # 2. 多 Agent 实时进展日志（每条 progress 都保留自己的 todo 快照）
        for pl in progress_log:
            p_at = pl.get('at', '')
            p_agent = pl.get('agent', '')
            p_text = pl.get('text', '')
            p_todos = pl.get('todos', [])
            p_state = pl.get('state', '')
            p_org = pl.get('org', '')
            if p_agent:
                related_agents.add(p_agent)
            # 累加资源消耗
            if pl.get('tokens'):
                total_tokens += pl['tokens']
                has_resource_data = True
            if pl.get('cost'):
                total_cost += pl['cost']
                has_resource_data = True
            if pl.get('elapsed'):
                total_elapsed += pl['elapsed']
                has_resource_data = True
            if p_text:
                entry = {
                    'at': p_at,
                    'kind': 'progress',
                    'text': p_text,
                    'agent': p_agent,
                    'agentLabel': pl.get('agentLabel', ''),
                    'state': p_state,
                    'org': p_org,
                }
                # 单条资源数据
                if pl.get('tokens'):
                    entry['tokens'] = pl['tokens']
                if pl.get('cost'):
                    entry['cost'] = pl['cost']
                if pl.get('elapsed'):
                    entry['elapsed'] = pl['elapsed']
                activity.append(entry)
            if p_todos:
                todos_entry = {
                    'at': p_at,
                    'kind': 'todos',
                    'items': p_todos,
                    'agent': p_agent,
                    'agentLabel': pl.get('agentLabel', ''),
                    'state': p_state,
                    'org': p_org,
                }
                # 计算 diff
                diff = _compute_todos_diff(prev_todos_snapshot, p_todos)
                if diff:
                    todos_entry['diff'] = diff
                activity.append(todos_entry)
                prev_todos_snapshot = p_todos

        # 仅当无法通过状态确定 Agent 时，才回退到最后一次上报的 Agent
        if not agent_id:
            last_pl = progress_log[-1]
            if last_pl.get('agent'):
                agent_id = last_pl.get('agent')
    else:
        # 兼容旧数据：仅使用 now/todos
        if now_text:
            activity.append({
                'at': updated_at,
                'kind': 'progress',
                'text': now_text,
                'agent': agent_id or '',
                'state': state,
                'org': org,
            })
        if todos:
            activity.append({
                'at': updated_at,
                'kind': 'todos',
                'items': todos,
                'agent': agent_id or '',
                'state': state,
                'org': org,
            })

    # 按时间排序，保证流转/进展穿插正确
    activity.sort(key=lambda x: x.get('at', ''))

    if agent_id:
        related_agents.add(agent_id)

    # ── 融合 Agent Session 活动（thinking / tool_result / user）──
    # 从 session JSONL 中提取 Agent 的思考过程和工具调用记录
    try:
        session_entries = []
        # 活跃任务：尝试按 task_id 精确匹配
        if state not in _TERMINAL_STATES:
            if agent_id:
                entries = get_agent_activity(agent_id, limit=30, task_id=task_id)
                session_entries.extend(entries)
            # 也从其他相关 Agent 获取
            for ra in related_agents:
                if ra != agent_id:
                    entries = get_agent_activity(ra, limit=20, task_id=task_id)
                    session_entries.extend(entries)
        else:
            # 已完成任务：基于关键词匹配
            title = task.get('title', '')
            keywords = _extract_keywords(title)
            if keywords:
                agents_to_scan = list(related_agents) if related_agents else ([agent_id] if agent_id else [])
                for ra in agents_to_scan[:5]:
                    entries = get_agent_activity_by_keywords(ra, keywords, limit=15)
                    session_entries.extend(entries)
        # 去重（通过 at+kind 去重避免重复）
        existing_keys = {(a.get('at', ''), a.get('kind', '')) for a in activity}
        for se in session_entries:
            key = (se.get('at', ''), se.get('kind', ''))
            if key not in existing_keys:
                activity.append(se)
                existing_keys.add(key)
        # 重新排序
        activity.sort(key=lambda x: x.get('at', ''))
    except Exception as e:
        log.warning(f'Session JSONL 融合失败 (task={task_id}): {e}')

    # ── 阶段耗时统计 ──
    phase_durations = _compute_phase_durations(flow_log)

    # ── Todos 汇总 ──
    todos_summary = _compute_todos_summary(todos)

    # ── 总耗时（首条 flow_log 到最后一条/当前） ──
    total_duration = None
    if flow_log:
        try:
            first_at = datetime.datetime.fromisoformat(flow_log[0].get('at', '').replace('Z', '+00:00'))
            if state in _TERMINAL_STATES and len(flow_log) >= 2:
                last_at = datetime.datetime.fromisoformat(flow_log[-1].get('at', '').replace('Z', '+00:00'))
            else:
                last_at = datetime.datetime.now(datetime.timezone.utc)
            dur = max(0, int((last_at - first_at).total_seconds()))
            if dur < 60:
                total_duration = f'{dur}秒'
            elif dur < 3600:
                total_duration = f'{dur // 60}分{dur % 60}秒'
            elif dur < 86400:
                h, rem = divmod(dur, 3600)
                total_duration = f'{h}小时{rem // 60}分'
            else:
                d, rem = divmod(dur, 86400)
                total_duration = f'{d}天{rem // 3600}小时'
        except Exception:
            pass

    result = {
        'ok': True,
        'taskId': task_id,
        'taskMeta': task_meta,
        'agentId': agent_id,
        'agentLabel': _STATE_LABELS.get(state, state),
        'lastActive': format_beijing(updated_at) if updated_at else None,
        'activity': activity,
        'activitySource': 'progress+session',
        'relatedAgents': sorted(list(related_agents)),
        'phaseDurations': phase_durations,
        'totalDuration': total_duration,
    }
    if todos_summary:
        result['todosSummary'] = todos_summary
    if has_resource_data:
        result['resourceSummary'] = {
            'totalTokens': total_tokens,
            'totalCost': round(total_cost, 4),
            'totalElapsedSec': total_elapsed,
        }
    return result


# 状态推进顺序（手动推进用）
_STATE_FLOW = workflow_manual_advance()
_STATE_LABELS = workflow_state_labels()
for _legacy_state, _canonical_state in _LEGACY_STATE_ALIASES.items():
    if _canonical_state in _STATE_LABELS and _legacy_state not in _STATE_LABELS:
        _STATE_LABELS[_legacy_state] = _STATE_LABELS[_canonical_state]


def dispatch_for_state(task_id, task, new_state, trigger='state-transition'):
    """推进/审批后自动派发对应 Agent（后台异步，不阻塞响应）。"""
    normalized_state = _normalize_state_name(new_state)
    source_meta = (task.get('sourceMeta') or {}) if isinstance(task.get('sourceMeta'), dict) else {}
    flow_mode = str(source_meta.get('flowMode') or '').strip().lower()
    preferred_dispatch_agent = str(source_meta.get('dispatchAgent') or '').strip()

    agent_id = None
    if flow_mode in {'direct', 'light'} and normalized_state == 'Doing' and preferred_dispatch_agent:
        agent_id = preferred_dispatch_agent
    if agent_id is None:
        agent_id = _STATE_AGENT_MAP.get(normalized_state)
    if agent_id is None and normalized_state in _ORG_RESOLVED_STATES:
        org = task.get('org', '')
        agent_id = _ORG_AGENT_MAP.get(org)
    if not agent_id:
        log.info(f'ℹ️ {task_id} 新状态 {new_state}（归一化: {normalized_state}）无对应 Agent，跳过自动派发')
        return
    runtime_agent_id = resolve_runtime_agent_id(agent_id)
    data_root = DATA

    def _queue_dispatch(t, s):
        s.update({
            'lastDispatchAt': now_iso(),
            'lastDispatchStatus': 'queued',
            'lastDispatchAgent': runtime_agent_id,
            'lastDispatchTrigger': trigger,
            'lastDispatchError': '',
        })
        _scheduler_add_flow(t, f'已入队派发：{new_state} → {runtime_agent_id}（{trigger}）', to=_STATE_LABELS.get(normalized_state, normalized_state))

    _update_task_scheduler(task_id, _queue_dispatch, data_root)

    title = task.get('title', '(无标题)')
    target_dept = task.get('targetDept', '')
    text_brief_hint = '\n'.join(_task_text_brief_lines(task))
    attachment_hint = '\n'.join(_task_attachment_summary_lines(task))
    context_parts = []
    if text_brief_hint:
        context_parts.append(text_brief_hint)
    if attachment_hint:
        context_parts.append(attachment_hint)
    attachment_block = ''.join(f'{part}\n' for part in context_parts if part)
    flow_mode = str(((task.get('sourceMeta') or {}) if isinstance(task.get('sourceMeta'), dict) else {}).get('flowMode') or '').strip().lower()
    direct_or_light = flow_mode in {'direct', 'light'}
    specialized_direct_dispatch = (
        direct_or_light
        and normalized_state == 'Doing'
        and agent_id not in {'chief_of_staff', 'planning', 'review_control', 'delivery_ops'}
    )
    route_hint = ''
    if specialized_direct_dispatch:
        route_hint = (
            '【流程约束】这是总裁办裁剪后的执行单，不进入产品规划部、评审质控部、交付运营部。\n'
            '【归档约束】禁止自行创建“总裁办交付目录”等私有归档目录。\n'
            '完成时必须先写一条 flow，再调用 kanban_update.py done：\n'
            f'python3 scripts/kanban_update.py flow {task_id} "{task.get("org", "")}" "总裁办" "✅ 已完成并归档：[一句话摘要]"\n'
            f'python3 scripts/kanban_update.py done {task_id} "<产出正文或产出文件路径>" "<一句话摘要>"\n'
            '如果产出是文件，直接把绝对路径传给 done；脚本会统一复制到总裁办交付目录。\n'
        )

    # 根据 agent_id 构造针对性消息
    _msgs = {
        'chief_of_staff': (
            f'📋 新任务需要你处理\n'
            f'任务ID: {task_id}\n'
            f'任务: {title}\n'
            f'固定流程: {flow_mode or "full"}\n'
            f'{"固定执行部门: " + target_dept + chr(10) if target_dept else ""}'
            f'{"固定阶段: " + " -> ".join(str(item) for item in ((task.get("sourceMeta") or {}).get("requiredStages") or [])) + chr(10) if ((task.get("sourceMeta") or {}).get("requiredStages") or []) else ""}'
            f'{attachment_block}'
            f'⚠️ 看板已有此任务，请勿重复创建。直接用 kanban_update.py 更新状态。\n'
            f'这是一条已建单任务。必须先用 extract_task_context.py 读取任务对象里的 TASK_FLOW_MODE / TASK_REQUIRED_STAGES / TASK_SKIP_*。\n'
            f'禁止再次运行 council 对这条已建单任务做二次分诊；必须严格按任务对象里的固定流程执行。'
        ),
        'planning': (
            f'📋 任务已到产品规划部，请起草方案\n'
            f'任务ID: {task_id}\n'
            f'任务: {title}\n'
            f'{attachment_block}'
            f'⚠️ 看板已有此任务记录，请勿重复创建。直接用 kanban_update.py state 更新状态。\n'
            f'请立即起草执行方案，走完完整流程（规划→评审→派发→执行）。'
        ),
        'review_control': (
            f'📋 产品规划部方案提交评审\n'
            f'任务ID: {task_id}\n'
            f'任务: {title}\n'
            f'{attachment_block}'
            f'⚠️ 看板已有此任务，请勿重复创建。\n'
            f'请评审产品规划部方案，给出通过或打回意见。'
        ),
        'delivery_ops': (
            f'📮 评审质控部已通过，请派发执行\n'
            f'任务ID: {task_id}\n'
            f'任务: {title}\n'
            f'{"建议派发部门: " + target_dept if target_dept else ""}\n'
            f'{attachment_block}'
            f'⚠️ 看板已有此任务，请勿重复创建。\n'
            f'请分析方案并派发给专项团队执行。'
        ),
    }
    msg = _msgs.get(agent_id, (
        f'📌 请处理任务\n'
        f'任务ID: {task_id}\n'
        f'任务: {title}\n'
        f'{attachment_block}'
        f'{route_hint}'
        f'⚠️ 看板已有此任务，请勿重复创建。直接用 kanban_update.py 更新状态。'
    ))

    def _do_dispatch():
        try:
            if not _check_gateway_alive():
                log.warning(f'⚠️ {task_id} 自动派发跳过: Gateway 未启动')
                _update_task_scheduler(task_id, lambda t, s: (
                    s.update({
                        'lastDispatchAt': now_iso(),
                        'lastDispatchStatus': 'gateway-offline',
                        'lastDispatchAgent': runtime_agent_id,
                        'lastDispatchTrigger': trigger,
                        'lastDispatchError': 'gateway offline',
                    }),
                    _scheduler_add_flow(t, f'派发失败：{runtime_agent_id}（{trigger}）原因：Gateway 未启动', to=t.get('org', ''))
                ), data_root)
                return
            max_retries = 2
            err = ''
            for attempt in range(1, max_retries + 1):
                log.info(f'🔄 自动派发 {task_id} → {runtime_agent_id} (第{attempt}次)...')
                result = _run_delegate_agent(runtime_agent_id, msg, timeout=300)
                if result.returncode == 0:
                    log.info(f'✅ {task_id} 自动派发成功 → {runtime_agent_id}')
                    _update_task_scheduler(task_id, lambda t, s: (
                        s.update({
                            'lastDispatchAt': now_iso(),
                            'lastDispatchStatus': 'success',
                            'lastDispatchAgent': runtime_agent_id,
                            'lastDispatchTrigger': trigger,
                            'lastDispatchError': '',
                        }),
                        _scheduler_add_flow(t, f'派发成功：{runtime_agent_id}（{trigger}）', to=t.get('org', ''))
                    ), data_root)
                    return
                err = _dispatch_error_text(result)
                log.warning(f'⚠️ {task_id} 自动派发失败(第{attempt}次): {err}')
                if attempt < max_retries:
                    import time
                    time.sleep(5)
            log.error(f'❌ {task_id} 自动派发最终失败 → {runtime_agent_id}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'failed',
                    'lastDispatchAgent': runtime_agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': err,
                }),
                _scheduler_add_flow(
                    t,
                    f'派发失败：{runtime_agent_id}（{trigger}）原因：{_dispatch_error_brief(err)}',
                    to=t.get('org', ''),
                )
            ), data_root)
        except subprocess.TimeoutExpired:
            log.error(f'❌ {task_id} 自动派发超时 → {runtime_agent_id}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'timeout',
                    'lastDispatchAgent': runtime_agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': 'timeout',
                }),
                _scheduler_add_flow(t, f'派发超时：{runtime_agent_id}（{trigger}）原因：timeout', to=t.get('org', ''))
            ), data_root)
        except Exception as e:
            log.warning(f'⚠️ {task_id} 自动派发异常: {e}')
            _update_task_scheduler(task_id, lambda t, s: (
                s.update({
                    'lastDispatchAt': now_iso(),
                    'lastDispatchStatus': 'error',
                    'lastDispatchAgent': runtime_agent_id,
                    'lastDispatchTrigger': trigger,
                    'lastDispatchError': str(e)[:200],
                }),
                _scheduler_add_flow(
                    t,
                    f'派发异常：{runtime_agent_id}（{trigger}）原因：{_dispatch_error_brief(str(e))}',
                    to=t.get('org', ''),
                )
            ), data_root)

    threading.Thread(target=_do_dispatch, daemon=True).start()
    log.info(f'🚀 {task_id} 推进后自动派发 → {runtime_agent_id}')


def handle_advance_state(task_id, comment=''):
    """手动推进任务到下一阶段（解卡用），推进后自动派发对应 Agent。"""
    tasks = load_tasks()
    task = next((t for t in tasks if t.get('id') == task_id), None)
    if not task:
        return {'ok': False, 'error': f'任务 {task_id} 不存在'}
    cur = task.get('state', '')
    normalized_cur = _normalize_state_name(cur)
    if normalized_cur not in _STATE_FLOW:
        return {'ok': False, 'error': f'任务 {task_id} 状态为 {cur}，无法推进'}
    _ensure_scheduler(task)
    _scheduler_snapshot(task, f'advance-before-{cur}')
    next_state, from_dept, to_dept, default_remark = _STATE_FLOW[normalized_cur]
    remark = comment or default_remark

    if normalized_cur == 'Planning' and next_state == 'ReviewControl':
        readiness = evaluate_review_readiness(task)
        if not readiness.get('ok'):
            reason = '；'.join(readiness.get('feedback', [])[:2]) or '缺少可审议方案'
            _scheduler_add_flow(task, f'阻止手动送审：{reason}', to=task.get('org', '产品规划部'))
            task['updatedAt'] = now_iso()
            save_tasks(tasks)
            return {'ok': False, 'error': f'任务 {task_id} 尚未满足送审条件：{reason}'}

    task['state'] = next_state
    task['org'] = to_dept
    task['now'] = f'⬇️ 手动推进：{remark}'
    task.setdefault('flow_log', []).append({
        'at': now_iso(),
        'from': from_dept,
        'to': to_dept,
        'remark': f'⬇️ 手动推进：{remark}'
    })
    _scheduler_mark_progress(task, f'手动推进 {cur} -> {next_state}')
    task['updatedAt'] = now_iso()
    save_tasks(tasks)

    # 🚀 推进后自动派发对应 Agent（Done 状态无需派发）
    if next_state not in _TERMINAL_STATES:
        dispatch_for_state(task_id, task, next_state)

    from_label = _STATE_LABELS.get(normalized_cur, cur)
    to_label = _STATE_LABELS.get(next_state, next_state)
    dispatched = ' (已自动派发 Agent)' if next_state not in _TERMINAL_STATES else ''
    return {'ok': True, 'message': f'{task_id} {from_label} → {to_label}{dispatched}'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # 只记录 4xx/5xx 错误请求
        if args and len(args) >= 1:
            status = str(args[0]) if args else ''
            if status.startswith('4') or status.startswith('5'):
                log.warning(f'{self.client_address[0]} {fmt % args}')

    def handle_error(self):
        pass  # 静默处理连接错误，避免 BrokenPipe 崩溃

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客户端断开连接，忽略

    def do_OPTIONS(self):
        self.send_response(200)
        cors_headers(self)
        self.end_headers()

    def send_json(self, data, code=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            cors_headers(self)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_file(self, path: pathlib.Path, mime='text/html; charset=utf-8'):
        if not path.exists():
            self.send_error(404)
            return
        try:
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            cors_headers(self)
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, rel_path):
        """从 dist/ 目录提供静态文件。"""
        safe = rel_path.replace('\\', '/').lstrip('/')
        if '..' in safe:
            self.send_error(403)
            return True
        fp = DIST / safe
        if fp.is_file():
            mime = _MIME_TYPES.get(fp.suffix.lower(), 'application/octet-stream')
            self.send_file(fp, mime)
            return True
        return False

    def do_GET(self):
        p = urlparse(self.path).path.rstrip('/')
        if p in ('', '/dashboard', '/dashboard.html'):
            self.send_file(DIST / 'index.html')
        elif p == '/healthz':
            checks = {'dataDir': DATA.is_dir(), 'tasksReadable': (DATA / 'tasks_source.json').exists()}
            checks['dataWritable'] = os.access(str(DATA), os.W_OK)
            all_ok = all(checks.values())
            self.send_json({'status': 'ok' if all_ok else 'degraded', 'ts': now_iso(), 'checks': checks})
        elif p == '/api/live-status':
            self.send_json(normalized_live_status_payload(DATA / 'live_status.json'))
        elif p == '/api/agent-config':
            self.send_json(read_json(DATA / 'agent_config.json'))
        elif p == '/api/model-change-log':
            self.send_json(read_json(DATA / 'model_change_log.json', []))
        elif p == '/api/last-result':
            self.send_json(read_json(DATA / 'last_model_change_result.json', {}))
        elif p == '/api/officials-stats':
            self.send_json(read_json(DATA / 'officials_stats.json', {}))
        elif p == '/api/remote-skills-list':
            self.send_json(get_remote_skills_list())
        elif p.startswith('/api/skill-content/'):
            # /api/skill-content/{agentId}/{skillName}
            parts = p.replace('/api/skill-content/', '').split('/', 1)
            if len(parts) == 2:
                self.send_json(read_skill_content(parts[0], parts[1]))
            else:
                self.send_json({'ok': False, 'error': 'Usage: /api/skill-content/{agentId}/{skillName}'}, 400)
        elif p.startswith('/api/task-activity/'):
            task_id = p.replace('/api/task-activity/', '')
            if not task_id:
                self.send_json({'ok': False, 'error': 'task_id required'}, 400)
            else:
                self.send_json(get_task_activity(task_id))
        elif p.startswith('/api/scheduler-state/'):
            task_id = p.replace('/api/scheduler-state/', '')
            if not task_id:
                self.send_json({'ok': False, 'error': 'task_id required'}, 400)
            else:
                self.send_json(get_scheduler_state(task_id))
        elif p == '/api/agents-status':
            self.send_json(get_agents_status())
        elif p.startswith('/api/agent-activity/'):
            agent_id = p.replace('/api/agent-activity/', '')
            if not agent_id or not _SAFE_NAME_RE.match(agent_id):
                self.send_json({'ok': False, 'error': 'invalid agent_id'}, 400)
            else:
                self.send_json({'ok': True, 'agentId': agent_id, 'activity': get_agent_activity(agent_id)})
        elif self._serve_static(p):
            pass  # 已由 _serve_static 处理 (JS/CSS/图片等)
        else:
            # SPA fallback：非 /api/ 路径返回 index.html
            if not p.startswith('/api/'):
                idx = DIST / 'index.html'
                if idx.exists():
                    self.send_file(idx)
                    return
            self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path).path.rstrip('/')
        length = int(self.headers.get('Content-Length', 0))
        if length > MAX_REQUEST_BODY:
            self.send_json({'ok': False, 'error': f'Request body too large (max {MAX_REQUEST_BODY} bytes)'}, 413)
            return
        raw = self.rfile.read(length) if length else b''
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            self.send_json({'ok': False, 'error': 'invalid JSON'}, 400)
            return

        if p == '/api/scheduler-scan':
            threshold_sec = body.get('thresholdSec', 180)
            try:
                result = handle_scheduler_scan(threshold_sec)
                self.send_json(result)
            except Exception as e:
                self.send_json({'ok': False, 'error': f'scheduler scan failed: {e}'}, 500)
            return

        if p == '/api/repair-flow-order':
            try:
                self.send_json(handle_repair_flow_order())
            except Exception as e:
                self.send_json({'ok': False, 'error': f'repair flow order failed: {e}'}, 500)
            return

        if p == '/api/scheduler-retry':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_retry(task_id, reason))
            return

        if p == '/api/scheduler-escalate':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_escalate(task_id, reason))
            return

        if p == '/api/scheduler-rollback':
            task_id = body.get('taskId', '').strip()
            reason = body.get('reason', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            self.send_json(handle_scheduler_rollback(task_id, reason))
            return

        if p == '/api/add-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', body.get('name', '')).strip()
            desc = body.get('description', '').strip() or skill_name
            trigger = body.get('trigger', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = add_skill_to_agent(agent_id, skill_name, desc, trigger)
            self.send_json(result)
            return

        if p == '/api/add-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            source_url = body.get('sourceUrl', '').strip()
            description = body.get('description', '').strip()
            if not agent_id or not skill_name or not source_url:
                self.send_json({'ok': False, 'error': 'agentId, skillName, and sourceUrl required'}, 400)
                return
            result = add_remote_skill(agent_id, skill_name, source_url, description)
            self.send_json(result)
            return

        if p == '/api/remote-skills-list':
            result = get_remote_skills_list()
            self.send_json(result)
            return

        if p == '/api/update-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = update_remote_skill(agent_id, skill_name)
            self.send_json(result)
            return

        if p == '/api/remove-remote-skill':
            agent_id = body.get('agentId', '').strip()
            skill_name = body.get('skillName', '').strip()
            if not agent_id or not skill_name:
                self.send_json({'ok': False, 'error': 'agentId and skillName required'}, 400)
                return
            result = remove_remote_skill(agent_id, skill_name)
            self.send_json(result)
            return

        if p == '/api/task-action':
            task_id = body.get('taskId', '').strip()
            action = body.get('action', '').strip()  # stop, cancel, resume
            reason = body.get('reason', '').strip() or f'需求方从看板{action}'
            if not task_id or action not in ('stop', 'cancel', 'resume'):
                self.send_json({'ok': False, 'error': 'taskId and action(stop/cancel/resume) required'}, 400)
                return
            result = handle_task_action(task_id, action, reason)
            self.send_json(result)
            return

        if p == '/api/archive-task':
            task_id = body.get('taskId', '').strip() if body.get('taskId') else ''
            archived = body.get('archived', True)
            archive_all = body.get('archiveAllDone', False)
            if not task_id and not archive_all:
                self.send_json({'ok': False, 'error': 'taskId or archiveAllDone required'}, 400)
                return
            result = handle_archive_task(task_id, archived, archive_all)
            self.send_json(result)
            return

        if p == '/api/task-todos':
            task_id = body.get('taskId', '').strip()
            todos = body.get('todos', [])  # [{id, title, status}]
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            # todos 输入校验
            if not isinstance(todos, list) or len(todos) > 200:
                self.send_json({'ok': False, 'error': 'todos must be a list (max 200 items)'}, 400)
                return
            valid_statuses = {'not-started', 'in-progress', 'completed'}
            for td in todos:
                if not isinstance(td, dict) or 'id' not in td or 'title' not in td:
                    self.send_json({'ok': False, 'error': 'each todo must have id and title'}, 400)
                    return
                if td.get('status', 'not-started') not in valid_statuses:
                    td['status'] = 'not-started'
            result = update_task_todos(task_id, todos)
            self.send_json(result)
            return

        if p == '/api/create-task':
            title = body.get('title', '').strip()
            org = body.get('org', '产品规划部').strip()
            official = body.get('official', '产品规划负责人').strip()
            priority = body.get('priority', 'normal').strip()
            template_id = body.get('templateId', '')
            params = body.get('params', {})
            mode_id = body.get('modeId', '').strip()
            flow_mode = body.get('flowMode', 'full').strip()
            if not title:
                self.send_json({'ok': False, 'error': 'title required'}, 400)
                return
            target_dept = body.get('targetDept', '').strip()
            result = handle_create_task(title, org, official, priority, template_id, params, target_dept, mode_id, flow_mode)
            self.send_json(result)
            return

        if p == '/api/review-action':
            task_id = body.get('taskId', '').strip()
            action = body.get('action', '').strip()  # approve, reject
            comment = body.get('comment', '').strip()
            if not task_id or action not in ('approve', 'reject'):
                self.send_json({'ok': False, 'error': 'taskId and action(approve/reject) required'}, 400)
                return
            result = handle_review_action(task_id, action, comment)
            self.send_json(result)
            return

        if p == '/api/advance-state':
            task_id = body.get('taskId', '').strip()
            comment = body.get('comment', '').strip()
            if not task_id:
                self.send_json({'ok': False, 'error': 'taskId required'}, 400)
                return
            result = handle_advance_state(task_id, comment)
            self.send_json(result)
            return

        if p == '/api/agent-wake':
            agent_id = body.get('agentId', '').strip()
            message = body.get('message', '').strip()
            if not agent_id:
                self.send_json({'ok': False, 'error': 'agentId required'}, 400)
                return
            result = wake_agent(agent_id, message)
            self.send_json(result)
            return

        if p == '/api/set-model':
            agent_id = body.get('agentId', '').strip()
            model = body.get('model', '').strip()
            if not agent_id or not model:
                self.send_json({'ok': False, 'error': 'agentId and model required'}, 400)
                return

            # Write to pending (atomic)
            pending_path = DATA / 'pending_model_changes.json'
            def update_pending(current):
                current = [x for x in current if x.get('agentId') != agent_id]
                current.append({'agentId': agent_id, 'model': model})
                return current
            atomic_json_update(pending_path, update_pending, [])

            # Async apply
            def apply_async():
                try:
                    _run_maintenance_script('apply_model_changes', timeout=30)
                    threading.Thread(target=_run_maintenance_script, args=('sync_agent_config',), daemon=True).start()
                except Exception as e:
                    print(f'[apply error] {e}', file=sys.stderr)

            threading.Thread(target=apply_async, daemon=True).start()
            self.send_json({'ok': True, 'message': f'Queued: {agent_id} → {model}'})
        else:
            self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description='现代公司架构看板服务器')
    parser.add_argument('--port', type=int, default=7891)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--cors', default=None, help='Allowed CORS origin (default: reflect request Origin header)')
    args = parser.parse_args()

    global ALLOWED_ORIGIN
    ALLOWED_ORIGIN = args.cors

    server = HTTPServer((args.host, args.port), Handler)
    log.info(f'现代公司架构看板启动 → http://{args.host}:{args.port}')
    print(f'   按 Ctrl+C 停止')

    def _scheduled_jobs_loop():
        import time
        time.sleep(4)
        while True:
            try:
                result = handle_run_due_scheduled_jobs()
                count = int((result or {}).get('count') or 0)
                if count:
                    log.info(f'⏰ 定时任务触发 {count} 项')
            except Exception as exc:
                log.warning(f'⚠️ 定时任务轮询失败: {exc}')
            time.sleep(30)

    # 启动恢复：重新派发上次被 kill 中断的 queued 任务
    threading.Timer(3.0, _startup_recover_queued_dispatches).start()
    threading.Thread(target=_scheduled_jobs_loop, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')


if __name__ == '__main__':
    main()

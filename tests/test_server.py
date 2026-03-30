"""tests for dashboard/server.py route handling"""
import importlib, json, os, pathlib, sys, threading, time
from http.client import HTTPConnection

# Add project paths
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'dashboard'))
sys.path.insert(0, str(ROOT / 'scripts'))


def _reload_server(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENCLAW_HOME", str(tmp_path / ".openclaw"))
    for name in ("server", "cron_jobs"):
        sys.modules.pop(name, None)
    import server as srv
    importlib.reload(srv)
    return srv


def test_healthz(tmp_path, monkeypatch):
    """GET /healthz returns 200 with status ok."""
    # Create minimal data dir
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'live_status.json').write_text('{}')
    (data_dir / 'agent_config.json').write_text('{}')

    # Import and patch server
    srv = _reload_server(monkeypatch, tmp_path)
    srv.DATA = data_dir

    from http.server import HTTPServer
    port = 18971

    httpd = HTTPServer(('127.0.0.1', port), srv.Handler)
    t = threading.Thread(target=httpd.handle_request, daemon=True)
    t.start()

    time.sleep(0.1)
    conn = HTTPConnection('127.0.0.1', port, timeout=5)
    conn.request('GET', '/healthz')
    resp = conn.getresponse()
    body = json.loads(resp.read())
    conn.close()

    assert resp.status == 200
    assert body['status'] in ('ok', 'degraded')

    httpd.server_close()


def test_scheduler_scan_force_blocks_stale_unclosed_task(tmp_path, monkeypatch):
    """Stale Doing task should be force-blocked when retry/escalation/rollback can no longer help."""
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'live_status.json').write_text('{}')
    (data_dir / 'agent_config.json').write_text('{}')
    (data_dir / 'tasks_source.json').write_text(json.dumps([
        {
            'id': 'T-STALE-1',
            'title': '排查新闻重复抓取问题',
            'state': 'Doing',
            'org': '执行中',
            'now': '已完成初步排查',
            'block': '无',
            'updatedAt': '2026-03-14T00:00:00Z',
            'todos': [
                {'id': '1', 'title': '排查问题', 'status': 'in-progress'},
            ],
            '_scheduler': {
                'enabled': True,
                'stallThresholdSec': 30,
                'maxRetry': 1,
                'retryCount': 1,
                'escalationLevel': 2,
                'autoRollback': True,
                'lastProgressAt': '2026-03-14T00:00:00Z',
                'stallSince': '2026-03-14T00:10:00Z',
                'lastDispatchStatus': 'success',
                'snapshot': {
                    'state': 'Doing',
                    'org': '执行中',
                    'now': '已完成初步排查',
                    'savedAt': '2026-03-14T00:00:00Z',
                    'note': 'init',
                },
            },
            'flow_log': [],
        }
    ]))

    srv = _reload_server(monkeypatch, tmp_path)
    srv.DATA = data_dir

    result = srv.handle_scheduler_scan(threshold_sec=30)
    tasks = json.loads((data_dir / 'tasks_source.json').read_text())
    task = tasks[0]

    assert result['ok'] is True
    assert any(action['action'] == 'force-block' for action in result['actions'])
    assert task['state'] == 'Blocked'
    assert task['org'] == '总裁办'
    assert 'Done / Blocked / 回传' in task['block']
    assert task['sourceMeta']['schedulerAutoBlocked'] is True
    assert task['sourceMeta']['blockerFeedback']['kind'] == 'workflow-closure'


def test_create_recurring_task_stays_scheduled_without_dispatch(tmp_path, monkeypatch):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'live_status.json').write_text('{}')
    (data_dir / 'agent_config.json').write_text('{}')
    (data_dir / 'tasks_source.json').write_text('[]')

    srv = _reload_server(monkeypatch, tmp_path)
    srv.DATA = data_dir

    dispatched: list[tuple[str, str, str]] = []

    def fake_dispatch(task_id, task, state, trigger=''):
        dispatched.append((task_id, state, trigger))

    srv.dispatch_for_state = fake_dispatch

    result = srv.handle_create_task(
        title='每日科技新闻总结与推送',
        org='总裁办',
        target_dept='工程研发部',
        priority='normal',
        flow_mode='light',
        params={
            'userBrief': '抓取这个页面的新闻 https://wallstreetcn.com/live/tech',
            'taskKind': 'recurring',
            'scheduleMode': 'daily',
            'scheduleLabel': '定时任务 · 每日 09:00',
            'scheduleTime': '09:00',
        },
    )

    tasks = json.loads((data_dir / 'tasks_source.json').read_text())
    task = tasks[0]

    assert result['ok'] is True
    assert result['taskId'].startswith('L-')
    assert dispatched == []
    assert task['state'] == 'Assigned'
    assert task['org'] == '调度器'
    assert task['now'] == '等待调度执行：定时任务 · 每日 09:00'
    assert task['output'] == '定时任务 · 每日 09:00'
    assert task['sourceMeta']['taskKind'] == 'recurring'
    assert task['sourceMeta']['scheduleLabel'] == '定时任务 · 每日 09:00'
    assert task['sourceMeta']['automationJobId'] == f"task-{task['id']}"

    jobs_payload = json.loads(srv.CRON_JOBS_PATH.read_text())
    assert jobs_payload['jobs'][0]['taskId'] == task['id']
    assert jobs_payload['jobs'][0]['schedule']['expr'] == '0 9 * * *'


def test_run_due_scheduled_jobs_dispatches_recurring_task(tmp_path, monkeypatch):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'live_status.json').write_text('{}')
    (data_dir / 'agent_config.json').write_text('{}')
    (data_dir / 'tasks_source.json').write_text(json.dumps([
        {
            'id': 'L-20260328-005',
            'title': '每日科技新闻总结与推送',
            'state': 'Assigned',
            'org': '调度器',
            'now': '等待调度执行：定时任务 · 每日 09:00',
            'block': '无',
            'output': '定时任务 · 每日 09:00',
            'targetDept': '工程研发部',
            'updatedAt': '2026-03-28T00:00:00Z',
            'flow_log': [{'at': '2026-03-28T00:00:00Z', 'from': '需求方', 'to': '总裁办', 'remark': '发起'}],
            'sourceMeta': {
                'flowMode': 'light',
                'dispatchAgent': 'engineering',
                'dispatchOrg': '工程研发部',
                'taskKind': 'recurring',
                'scheduleMode': 'daily',
                'scheduleTime': '09:00',
                'scheduleLabel': '定时任务 · 每日 09:00',
            },
        }
    ]))

    srv = _reload_server(monkeypatch, tmp_path)
    srv.DATA = data_dir
    job_id = srv.upsert_job_for_task(json.loads((data_dir / 'tasks_source.json').read_text())[0])
    jobs_payload = json.loads(srv.CRON_JOBS_PATH.read_text())
    jobs_payload['jobs'][0]['state']['nextRunAtMs'] = int(time.time() * 1000) - 1000
    jobs_payload['jobs'][0]['state']['running'] = False
    srv.CRON_JOBS_PATH.write_text(json.dumps(jobs_payload, ensure_ascii=False, indent=2))

    dispatched: list[tuple[str, str, str]] = []

    def fake_dispatch(task_id, task, state, trigger=''):
        dispatched.append((task_id, state, trigger))

    srv.dispatch_for_state = fake_dispatch

    result = srv.handle_run_due_scheduled_jobs()
    tasks = json.loads((data_dir / 'tasks_source.json').read_text())
    task = tasks[0]
    jobs_payload = json.loads(srv.CRON_JOBS_PATH.read_text())

    assert result['ok'] is True
    assert result['count'] == 1
    assert dispatched == [('L-20260328-005', 'Doing', 'cron-due')]
    assert task['state'] == 'Doing'
    assert task['org'] == '工程研发部'
    assert '调度触发执行' in task['now']
    assert jobs_payload['jobs'][0]['id'] == job_id
    assert jobs_payload['jobs'][0]['state']['lastRunStatus'] == 'queued'
    assert jobs_payload['jobs'][0]['state']['nextRunAtMs'] > int(time.time() * 1000)


def test_reconcile_recurring_done_task_back_to_scheduler(tmp_path, monkeypatch):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    (data_dir / 'live_status.json').write_text('{}')
    (data_dir / 'agent_config.json').write_text('{}')
    (data_dir / 'tasks_source.json').write_text(json.dumps([
        {
            'id': 'L-20260328-005',
            'title': '每日科技新闻总结与推送',
            'state': 'Done',
            'org': '完成',
            'now': '✅ 已完成',
            'block': '',
            'output': '/tmp/out.md',
            'updatedAt': '2026-03-29T01:05:00Z',
            'flow_log': [{'at': '2026-03-28T00:00:00Z', 'from': '需求方', 'to': '总裁办', 'remark': '发起'}],
            'sourceMeta': {
                'flowMode': 'light',
                'dispatchAgent': 'engineering',
                'taskKind': 'recurring',
                'scheduleMode': 'daily',
                'scheduleTime': '09:00',
                'scheduleLabel': '定时任务 · 每日 09:00',
            },
        }
    ]))

    srv = _reload_server(monkeypatch, tmp_path)
    srv.DATA = data_dir
    srv.handle_run_due_scheduled_jobs()
    tasks = json.loads((data_dir / 'tasks_source.json').read_text())
    task = tasks[0]

    assert task['state'] == 'Assigned'
    assert task['org'] == '调度器'
    assert task['now'] == '等待调度执行：定时任务 · 每日 09:00'

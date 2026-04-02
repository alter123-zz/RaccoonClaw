"""tests for scripts/kanban_update.py"""
import json, pathlib, sys

# Ensure scripts/ is importable
SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import kanban_update as kb


def test_create_and_get(tmp_path):
    """kanban create + get round-trip."""
    tasks_file = tmp_path / 'tasks_source.json'
    tasks_file.write_text('[]')

    # Patch TASKS_FILE
    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_create('TEST-001', '测试任务创建和查询功能验证', 'Inbox', '工程研发部', '工程研发负责人')
        tasks = json.loads(tasks_file.read_text())
        assert any(t.get('id') == 'TEST-001' for t in tasks)
        t = next(t for t in tasks if t['id'] == 'TEST-001')
        assert t['title'] == '测试任务创建和查询功能验证'
        assert t['state'] == 'Inbox'
        assert t['org'] == '工程研发部'
    finally:
        kb.TASKS_FILE = original


def test_move_state(tmp_path):
    """kanban move changes task state."""
    tasks_file = tmp_path / 'tasks_source.json'
    tasks_file.write_text(json.dumps([
        {'id': 'T-1', 'title': 'test', 'state': 'Inbox'}
    ]))

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_state('T-1', 'Doing')
        tasks = json.loads(tasks_file.read_text())
        assert tasks[0]['state'] == 'Doing'
    finally:
        kb.TASKS_FILE = original


def test_full_flow_task_cannot_enter_done_before_callback(tmp_path):
    """full 流程任务在“回传总裁办”未完成前不能直接 Done。"""
    tasks_file = tmp_path / 'tasks_source.json'
    tasks_file.write_text(json.dumps([
        {
            'id': 'T-3',
            'title': 'full flow test',
            'state': 'Assigned',
            'org': '交付运营部',
            'sourceMeta': {
                'flowMode': 'full',
                'requiredStages': ['planning', 'review', 'dispatch', 'execution'],
            },
            'todos': [
                {'id': '1', 'title': '分析需求', 'status': 'completed'},
                {'id': '2', 'title': '起草方案', 'status': 'completed'},
                {'id': '3', 'title': '评审质控', 'status': 'completed'},
                {'id': '4', 'title': '交付执行', 'status': 'completed'},
                {'id': '5', 'title': '回传总裁办', 'status': 'in-progress'},
            ],
        }
    ], ensure_ascii=False))

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        result = kb.cmd_state('T-3', 'Done', '执行完成')
        tasks = json.loads(tasks_file.read_text())
        assert result == 2
        assert tasks[0]['state'] == 'Assigned'
        assert tasks[0]['todos'][-1]['status'] == 'in-progress'
    finally:
        kb.TASKS_FILE = original


def test_full_flow_task_can_enter_done_after_callback(tmp_path):
    """full 流程任务在“回传总裁办”完成后可以进入 Done。"""
    tasks_file = tmp_path / 'tasks_source.json'
    tasks_file.write_text(json.dumps([
        {
            'id': 'T-4',
            'title': 'full flow done test',
            'state': 'Assigned',
            'org': '交付运营部',
            'sourceMeta': {
                'flowMode': 'full',
                'requiredStages': ['planning', 'review', 'dispatch', 'execution'],
            },
            'todos': [
                {'id': '1', 'title': '分析需求', 'status': 'completed'},
                {'id': '2', 'title': '起草方案', 'status': 'completed'},
                {'id': '3', 'title': '评审质控', 'status': 'completed'},
                {'id': '4', 'title': '交付执行', 'status': 'completed'},
                {'id': '5', 'title': '回传总裁办', 'status': 'completed'},
            ],
        }
    ], ensure_ascii=False))

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        result = kb.cmd_state('T-4', 'Done', '执行完成')
        tasks = json.loads(tasks_file.read_text())
        assert result == 0
        assert tasks[0]['state'] == 'Done'
        assert tasks[0]['org'] == '完成'
    finally:
        kb.TASKS_FILE = original


def test_block_and_unblock(tmp_path):
    """kanban block/unblock round-trip."""
    tasks_file = tmp_path / 'tasks_source.json'
    tasks_file.write_text(json.dumps([
        {'id': 'T-2', 'title': 'blocker test', 'state': 'Doing'}
    ]))

    original = kb.TASKS_FILE
    kb.TASKS_FILE = tasks_file
    try:
        kb.cmd_block('T-2', '等待依赖')
        tasks = json.loads(tasks_file.read_text())
        assert tasks[0]['state'] == 'Blocked'
        assert tasks[0]['block'] == '等待依赖'
    finally:
        kb.TASKS_FILE = original

#!/usr/bin/env python3
import json
import pathlib
import time
import datetime
import traceback
import logging
from file_lock import atomic_json_write, atomic_json_read
from agent_registry import agent_registry_by_id, sync_agent_labels, canonical_agent_id
from runtime_paths import canonical_data_dir
from task_ids import is_normal_task_id
from utils import beijing_now, format_beijing

log = logging.getLogger('sync_runtime')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = canonical_data_dir()
DATA.mkdir(exist_ok=True)
SYNC_STATUS = DATA / 'sync_status.json'
SESSIONS_ROOT = pathlib.Path.home() / '.openclaw' / 'agents'
AGENT_REGISTRY = agent_registry_by_id()
AGENT_LABELS = sync_agent_labels()


def write_status(**kwargs):
    atomic_json_write(SYNC_STATUS, kwargs)


def ms_to_str(ts_ms):
    if not ts_ms:
        return '-'
    try:
        return format_beijing(ts_ms)
    except Exception:
        return '-'


def state_from_session(age_ms, aborted):
    if aborted:
        return 'Blocked'
    # 用户视角里，“刚刚还在跑”的会话不该在 2 分钟后立刻掉到 Review。
    # 放宽到 15 分钟，保证任务看板能稳定看到最近活跃的 OpenClaw 运行会话。
    if age_ms <= 15 * 60 * 1000:
        return 'Doing'
    if age_ms <= 60 * 60 * 1000:
        return 'Review'
    return 'Next'


def detect_official(agent_id):
    resolved_id = canonical_agent_id(agent_id)
    meta = AGENT_REGISTRY.get(resolved_id)
    if meta:
        return meta['displayRole'], meta['label']
    label_meta = AGENT_LABELS.get(resolved_id) or AGENT_LABELS.get(agent_id) or AGENT_LABELS.get('delivery_ops') or {
        'role': '交付运营负责人',
        'label': '交付运营部',
    }
    return label_meta['role'], label_meta['label']


def build_session_flow(agent_id, org, updated_at, session_key):
    resolved_id = canonical_agent_id(agent_id)
    if resolved_id != 'chief_of_staff':
        return None, []

    at = ms_to_str(updated_at)
    return (
        {'direct': '总裁办直办'},
        [{
            'at': at,
            'from': '总裁办',
            'to': '总裁办',
            'remark': f'总裁办直办 · {session_key}',
        }],
    )


def load_activity(session_file, limit=12):
    p = pathlib.Path(session_file or '')
    if not p.exists():
        return []
    rows = []
    try:
        lines = p.read_text(errors='ignore').splitlines()
    except Exception:
        return []

    # Read all valid JSON lines first
    events = []
    for ln in lines:
        try:
            item = json.loads(ln)
            events.append(item)
        except:
            continue

    # Process events to extract meaningful activity
    # We want to show what the agent is *thinking* or *doing*
    for item in reversed(events):
        msg = item.get('message') or {}
        role = msg.get('role')
        ts = item.get('timestamp') or ''

        if role == 'toolResult':
            tool = msg.get('toolName', '-')
            details = msg.get('details') or {}
            # If tool output is short, show it
            content = msg.get('content', [{'text': ''}])[0].get('text', '')
            if len(content) < 50:
                text = f"Tool '{tool}' returned: {content}"
            else:
                text = f"Tool '{tool}' finished"
            rows.append({'at': ts, 'kind': 'tool', 'text': text})

        elif role == 'assistant':
            text = ''
            for c in msg.get('content', []):
                if c.get('type') == 'text' and c.get('text'):
                    raw_text = c.get('text').strip()
                    # Clean up common prefixes
                    clean_text = raw_text.replace('[[reply_to_current]]', '').strip()
                    if clean_text:
                        text = clean_text
                    break
            if text:
                # Prioritize showing the "thought" - usually the first few sentences
                summary = text.split('\n')[0]
                if len(summary) > 200:
                    summary = summary[:200] + '...'
                rows.append({'at': ts, 'kind': 'assistant', 'text': summary})
                
        elif role == 'user':
             # Also show what user asked, can be context relevant
             text = ''
             for c in msg.get('content', []):
                if c.get('type') == 'text':
                     text = c.get('text', '')[:100]
             if text:
                 rows.append({'at': ts, 'kind': 'user', 'text': f"User: {text}..."})

        if len(rows) >= limit:
            break

    # Re-order to chronological for display if needed, but the caller usually takes the first (latest)
    return rows


def build_task(agent_id, session_key, row, now_ms):
    session_id = row.get('sessionId') or session_key
    updated_at = row.get('updatedAt') or 0
    age_ms = max(0, now_ms - updated_at) if updated_at else 99 * 24 * 3600 * 1000
    aborted = bool(row.get('abortedLastRun'))
    state = state_from_session(age_ms, aborted)

    official, org = detect_official(agent_id)
    flow, flow_log = build_session_flow(agent_id, org, updated_at, session_key)
    channel = row.get('lastChannel') or (row.get('origin') or {}).get('channel') or '-'
    session_file = row.get('sessionFile', '')
    
    # 尝试从 activity 获取更有意义的当前状态描述
    latest_act = '等待指令'
    acts = load_activity(session_file, limit=5)
    latest_kind = acts[0]['kind'] if acts else None
    
    # If the absolute latest is a tool result, look for the preceding assistant thought
    # because that explains *why* the tool was called.
    if acts:
        first_act = acts[0]
        if first_act['kind'] == 'tool' and len(acts) > 1:
            # Look for next assistant message (which is actually previous in time)
            for next_act in acts[1:]:
                if next_act['kind'] == 'assistant':
                    latest_act = f"正在执行: {next_act['text'][:80]}"
                    break
            else:
                latest_act = first_act['text'][:60]
        elif first_act['kind'] == 'assistant':
             latest_act = f"思考中: {first_act['text'][:80]}"
        else:
             latest_act = acts[0]['text'][:60]

    is_main_session = session_key == f'agent:{agent_id}:main' or session_key.endswith(':main')
    idle_main_session = (
        is_main_session
        and not aborted
        and state == 'Doing'
        and age_ms >= 60 * 1000
        and latest_kind == 'assistant'
    )
    if idle_main_session:
        state = 'Next'
        latest_act = '待命中: 已完成最近一次调度回复'
    
    title_label = (row.get('origin') or {}).get('label') or session_key
    # 清洗会话标题：agent:xxx:cron:uuid → 定时任务, agent:xxx:subagent:uuid → 子任务
    import re
    if re.match(r'agent:\w+:cron:', title_label):
        title = f"{org}定时任务"
    elif re.match(r'agent:\w+:subagent:', title_label):
        title = f"{org}子任务"
    elif title_label == session_key or len(title_label) > 40:
        title = f"{org}会话"
    else:
        title = f"{title_label}"
    
    task = {
        'id': f"OC-{agent_id}-{str(session_id)[:8]}",
        'title': title,
        'official': official,
        'org': org,
        'state': state,
        'now': latest_act,
        'eta': ms_to_str(updated_at),
        'block': '上次运行中断' if aborted else '无',
        'output': session_file,
        'ac': '来自 OpenClaw runtime sessions 的实时映射',
        'activity': load_activity(session_file, limit=10),
        'sourceMeta': {
            'agentId': agent_id,
            'sessionKey': session_key,
            'sessionId': session_id,
            'updatedAt': updated_at,
            'ageMs': age_ms,
            'systemSent': bool(row.get('systemSent')),
            'abortedLastRun': aborted,
            'inputTokens': row.get('inputTokens'),
            'outputTokens': row.get('outputTokens'),
            'totalTokens': row.get('totalTokens'),
        }
    }
    if flow:
        task['flow'] = flow
    if flow_log:
        task['flow_log'] = flow_log
    return task


def main():
    start = time.time()
    now = beijing_now().strftime('%Y-%m-%d %H:%M:%S')
    now_ms = int(time.time() * 1000)

    try:
        tasks = []
        scan_files = 0

        if SESSIONS_ROOT.exists():
            for agent_dir in sorted(SESSIONS_ROOT.iterdir()):
                if not agent_dir.is_dir():
                    continue
                agent_id = agent_dir.name
                sessions_file = agent_dir / 'sessions' / 'sessions.json'
                if not sessions_file.exists():
                    continue
                scan_files += 1

                try:
                    raw = json.loads(sessions_file.read_text())
                except Exception:
                    continue

                if not isinstance(raw, dict):
                    continue

                for session_key, row in raw.items():
                    if not isinstance(row, dict):
                        continue
                    tasks.append(build_task(agent_id, session_key, row, now_ms))

        # merge mission control tasks (最小接入)
        mc_tasks_file = DATA / 'mission_control_tasks.json'
        if mc_tasks_file.exists():
            try:
                mc_tasks = json.loads(mc_tasks_file.read_text())
                if isinstance(mc_tasks, list):
                    tasks.extend(mc_tasks)
            except Exception:
                pass

        # merge manual parallel tasks (用于协作看板并行展示)
        manual_tasks_file = DATA / 'manual_parallel_tasks.json'
        if manual_tasks_file.exists():
            try:
                manual_tasks = json.loads(manual_tasks_file.read_text())
                if isinstance(manual_tasks, list):
                    tasks.extend(manual_tasks)
            except Exception:
                pass

        tasks.sort(key=lambda x: x.get('sourceMeta', {}).get('updatedAt', 0), reverse=True)

        # 去重（同一 id 只保留第一个=最新的）
        seen_ids = set()
        deduped = []
        for t in tasks:
            if t['id'] not in seen_ids:
                seen_ids.add(t['id'])
                deduped.append(t)
        tasks = deduped

        # ── 过滤掉非正式任务且非活跃的系统会话，防止看板噪音 ──
        # 规则: 仅保留 24小时内更新的活跃会话，且排除 cron/subagent 等纯后台任务
        filtered_tasks = []
        one_day_ago = now_ms - 24 * 3600 * 1000
        for t in tasks:
            # 始终保留正式任务（如果有的话，虽然这里主要是 OC 任务，但以防万一）
            if is_normal_task_id(str(t.get('id') or '')):
                filtered_tasks.append(t)
                continue
            
            # OC 任务过滤
            updated = t.get('sourceMeta', {}).get('updatedAt', 0)
            title = t.get('title', '')
            
            # 1. 排除太旧的 (超过24小时)
            if updated < one_day_ago:
                continue
            
            # 2. 排除纯后台 cron / subagent 任务，除非它们正在报错
            if '定时任务' in title or '子任务' in title:
                # 只有当它 block 或者 error 时才显示，否则视为噪音
                if t.get('state') != 'Blocked':
                    continue

            # 3. 只排除真正已沉寂的 OC 会话。
            # Doing/Review/Blocked 都属于用户视角的“仍值得在看板可见”的运行态：
            # - Doing: 正在执行
            # - Review: 刚执行过，仍在短时间活跃窗口内
            # - Blocked: 需要关注
            state = t.get('state')
            # state_from_session: < 2min = Doing, < 60min = Review, else = Next
            if state not in ('Doing', 'Review', 'Blocked'):
                continue

            filtered_tasks.append(t)
        
        tasks = filtered_tasks
        
        # ── 保留已有的正式任务（不覆盖需求方发起记录）──
        # 正式任务的 now 字段由 Agent 自己通过 kanban_update.py progress 命令主动上报，
        # 不再从会话日志中被动抓取。这里只做合并，不做 activity 映射。
        existing_tasks_file = DATA / 'tasks_source.json'
        if existing_tasks_file.exists():
            try:
                existing = json.loads(existing_tasks_file.read_text())
                formal_existing = [t for t in existing if is_normal_task_id(str(t.get('id') or ''))]
                
                # 去掉 tasks 里已有的正式任务（以防重复），再把正式任务放到最前面
                tasks = [t for t in tasks if not is_normal_task_id(str(t.get('id') or ''))]
                tasks = formal_existing + tasks
            except Exception as e:
                log.error(f'merge existing JJC tasks failed: {e}')
                pass

        atomic_json_write(DATA / 'tasks_source.json', tasks)

        duration_ms = int((time.time() - start) * 1000)
        write_status(
            ok=True,
            lastSyncAt=now,
            durationMs=duration_ms,
            source='openclaw_runtime_sessions',
            recordCount=len(tasks),
            scannedSessionFiles=scan_files,
            missingFields={},
            error=None,
        )
        log.info(f'synced {len(tasks)} tasks from openclaw runtime in {duration_ms}ms')

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        write_status(
            ok=False,
            lastSyncAt=now,
            durationMs=duration_ms,
            source='openclaw_runtime_sessions',
            recordCount=0,
            missingFields={},
            error=f'{type(e).__name__}: {e}',
            traceback=traceback.format_exc(limit=3),
        )
        raise


if __name__ == '__main__':
    main()

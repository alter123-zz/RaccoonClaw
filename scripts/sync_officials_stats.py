#!/usr/bin/env python3
"""同步各团队角色统计数据 → data/officials_stats.json"""
import json, pathlib, datetime, logging
from file_lock import atomic_json_write
from agent_registry import officials_registry, resolve_runtime_agent_id, runtime_candidate_ids
from runtime_paths import canonical_data_dir
from task_ids import is_normal_task_id
from utils import beijing_now, format_beijing, parse_datetime

log = logging.getLogger('officials')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = canonical_data_dir()
AGENTS_ROOT = pathlib.Path.home() / '.openclaw' / 'agents'
OPENCLAW_CFG = pathlib.Path.home() / '.openclaw' / 'openclaw.json'

# Anthropic 定价（每1M token，美元）
MODEL_PRICING = {
    'openai-codex/gpt-5.4':         {'in':0,   'out':0,    'cr':0,    'cw':0},
    'anthropic/claude-sonnet-4-6':  {'in':3.0, 'out':15.0, 'cr':0.30, 'cw':3.75},
    'anthropic/claude-opus-4-5':    {'in':15.0,'out':75.0, 'cr':1.50, 'cw':18.75},
    'anthropic/claude-haiku-3-5':   {'in':0.8, 'out':4.0,  'cr':0.08, 'cw':1.0},
    'openai/gpt-4o':                {'in':2.5, 'out':10.0, 'cr':1.25, 'cw':0},
    'openai/gpt-4o-mini':           {'in':0.15,'out':0.6,  'cr':0.075,'cw':0},
    'google/gemini-2.0-flash':      {'in':0.075,'out':0.3, 'cr':0,    'cw':0},
    'google/gemini-2.5-pro':        {'in':1.25,'out':10.0, 'cr':0,    'cw':0},
}

OFFICIALS = officials_registry()

def rj(p, d):
    try: return json.loads(pathlib.Path(p).read_text())
    except Exception: return d


# Pre-load openclaw config once (avoid re-reading per agent)
_OPENCLAW_CACHE = None

def _load_openclaw_cfg():
    global _OPENCLAW_CACHE
    if _OPENCLAW_CACHE is None:
        _OPENCLAW_CACHE = rj(OPENCLAW_CFG, {})
    return _OPENCLAW_CACHE


def normalize_model(model_value, fallback='openai-codex/gpt-5.4'):
    if isinstance(model_value, str) and model_value:
        return model_value
    if isinstance(model_value, dict):
        return model_value.get('primary') or model_value.get('id') or fallback
    return fallback

def get_model(agent_id):
    runtime_id = resolve_runtime_agent_id(agent_id)
    cfg = _load_openclaw_cfg()
    default = normalize_model(cfg.get('agents',{}).get('defaults',{}).get('model',{}), 'openai-codex/gpt-5.4')
    for a in cfg.get('agents',{}).get('list',[]):
        if a.get('id') == runtime_id:
            return normalize_model(a.get('model', default), default)
    for candidate in runtime_candidate_ids(agent_id):
        for a in cfg.get('agents',{}).get('list',[]):
            if a.get('id') == candidate:
                return normalize_model(a.get('model', default), default)
    return default

def scan_agent(agent_id):
    """从 sessions.json 读取 token 统计（累计所有 session）"""
    runtime_id = resolve_runtime_agent_id(agent_id)
    sj = AGENTS_ROOT / runtime_id / 'sessions' / 'sessions.json'
    if not sj.exists():
        for candidate in runtime_candidate_ids(agent_id):
            maybe = AGENTS_ROOT / candidate / 'sessions' / 'sessions.json'
            if maybe.exists():
                sj = maybe
                runtime_id = candidate
                break
    if not sj.exists():
        return {'tokens_in':0,'tokens_out':0,'cache_read':0,'cache_write':0,'sessions':0,'last_active':None,'messages':0}
    
    data = rj(sj, {})
    tin = tout = cr = cw = 0
    last_ts = None
    
    for sid, v in data.items():
        tin += v.get('inputTokens', 0) or 0
        tout += v.get('outputTokens', 0) or 0
        cr  += v.get('cacheRead', 0) or 0
        cw  += v.get('cacheWrite', 0) or 0
        ts = v.get('updatedAt')
        if ts:
            try:
                t = parse_datetime(ts)
                if t and (last_ts is None or t > last_ts):
                    last_ts = t
            except Exception: pass
    
    # Estimate message count from most recent session JSONL
    msg_count = 0
    if data:
        try:
            sf_key = max(data.keys(), key=lambda k: data[k].get('updatedAt',0) or 0, default=None)
        except Exception:
            sf_key = None
    else:
        sf_key = None
    if sf_key and data[sf_key].get('sessionFile'):
        sf = AGENTS_ROOT / runtime_id / 'sessions' / pathlib.Path(data[sf_key]['sessionFile']).name
        try:
            lines = sf.read_text(errors='ignore').splitlines()
            for ln in lines:
                try:
                    e = json.loads(ln)
                    if e.get('type') == 'message' and e.get('message',{}).get('role') == 'assistant':
                        msg_count += 1
                except Exception: pass
        except Exception: pass

    return {
        'tokens_in': tin, 'tokens_out': tout,
        'cache_read': cr, 'cache_write': cw,
        'sessions': len(data),
        'last_active': format_beijing(last_ts, '%Y-%m-%d %H:%M') if last_ts else None,
        'messages': msg_count,
    }

def calc_cost(s, model):
    p = MODEL_PRICING.get(model, MODEL_PRICING['openai-codex/gpt-5.4'])
    usd = (s['tokens_in']/1e6*p['in'] + s['tokens_out']/1e6*p['out']
         + s['cache_read']/1e6*p['cr'] + s['cache_write']/1e6*p['cw'])
    return round(usd, 4)

def get_task_stats(org_label, tasks):
    done   = [t for t in tasks if t.get('state')=='Done' and t.get('org')==org_label]
    active = [t for t in tasks if t.get('state') in ('Doing','Review','Assigned') and t.get('org')==org_label]
    fl = sum(1 for t in tasks for f in t.get('flow_log',[])
             if f.get('from')==org_label or f.get('to')==org_label)
    # 参与的正式任务列表
    participated = []
    for t in tasks:
        if not is_normal_task_id(str(t.get('id') or '')):
            continue
        for f in t.get('flow_log',[]):
            if f.get('from')==org_label or f.get('to')==org_label:
                if t['id'] not in [x['id'] for x in participated]:
                    participated.append({'id':t['id'],'title':t.get('title',''),'state':t.get('state','')})
                break
    return {'tasks_done':len(done),'tasks_active':len(active),
            'flow_participations':fl,'participated_edicts':participated}

def get_hb(agent_id, live_tasks):
    candidates = {resolve_runtime_agent_id(agent_id), *runtime_candidate_ids(agent_id), agent_id}
    for t in live_tasks:
        if t.get('sourceMeta',{}).get('agentId') in candidates and t.get('heartbeat'):
            return t['heartbeat']
    return {'status':'idle','label':'⚪ 待命','ageSec':None}

def main():
    tasks = rj(DATA/'tasks_source.json', [])
    live  = rj(DATA/'live_status.json', {})
    live_tasks = live.get('tasks', [])

    result = []
    for off in OFFICIALS:
        model   = get_model(off['id'])
        ss      = scan_agent(off['id'])
        ts      = get_task_stats(off['label'], tasks)
        hb      = get_hb(off['id'], live_tasks)
        cost_usd = calc_cost(ss, model)

        result.append({
            **off,
            'model': model,
            'model_short': model.split('/')[-1] if isinstance(model, str) and '/' in model else str(model),
            'sessions': ss['sessions'],
            'tokens_in': ss['tokens_in'],
            'tokens_out': ss['tokens_out'],
            'cache_read': ss['cache_read'],
            'cache_write': ss['cache_write'],
            'tokens_total': ss['tokens_in'] + ss['tokens_out'],
            'messages': ss['messages'],
            'cost_usd': cost_usd,
            'cost_cny': round(cost_usd * 7.25, 2),
            'last_active': ss['last_active'],
            'heartbeat': hb,
            'tasks_done': ts['tasks_done'],
            'tasks_active': ts['tasks_active'],
            'flow_participations': ts['flow_participations'],
            'participated_edicts': ts['participated_edicts'],
            'merit_score': ts['tasks_done']*10 + ts['flow_participations']*2 + min(ss['sessions'],20),
        })

    result.sort(key=lambda x: x['merit_score'], reverse=True)
    for i, r in enumerate(result): r['merit_rank'] = i+1

    totals = {
        'tokens_total': sum(r['tokens_total'] for r in result),
        'cache_total':  sum(r['cache_read']+r['cache_write'] for r in result),
        'cost_usd':     round(sum(r['cost_usd'] for r in result), 2),
        'cost_cny':     round(sum(r['cost_cny'] for r in result), 2),
        'tasks_done':   sum(r['tasks_done'] for r in result),
    }
    top = max(result, key=lambda x: x['merit_score'], default={})

    payload = {
        'generatedAt': beijing_now().strftime('%Y-%m-%d %H:%M:%S'),
        'officials': result,
        'totals': totals,
        'top_official': top.get('label',''),
    }
    atomic_json_write(DATA/'officials_stats.json', payload)
    log.info(f'{len(result)} officials | cost=¥{totals["cost_cny"]} | top={top.get("label","")}')

if __name__ == '__main__':
    main()

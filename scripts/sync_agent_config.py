#!/usr/bin/env python3
"""
同步 openclaw.json 中的 agent 配置 → data/agent_config.json
支持自动发现 agent workspace 下的 Skills 目录
"""
import filecmp, json, pathlib, datetime, logging, shutil
from file_lock import atomic_json_write
from agent_registry import sync_agent_labels, canonical_agent_id
from runtime_paths import (
    agent_dir,
    canonical_data_dir,
    canonical_workspace_dir,
    openclaw_config_path,
    openclaw_home,
    workspace_dir_for,
)
from utils import beijing_now

log = logging.getLogger('sync_agent_config')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

# Auto-detect project root (parent of scripts/)
BASE = pathlib.Path(__file__).parent.parent
DATA = canonical_data_dir()
OPENCLAW_CFG = openclaw_config_path()

ID_LABEL = sync_agent_labels()

PROVIDER_LABELS = {
    'anthropic': 'Anthropic',
    'openai': 'OpenAI',
    'openai-codex': 'OpenAI Codex',
    'google': 'Google',
    'copilot': 'Copilot',
    'github-copilot': 'GitHub Copilot',
    'minimax-cn': 'MiniMax',
    'glm': 'GLM',
}


def _skill_contains_legacy_qclaw(skill_dir: pathlib.Path) -> bool:
    skill_md = skill_dir / 'SKILL.md'
    if 'qclaw' in skill_dir.name.lower():
        return True
    if not skill_md.exists():
        return False
    try:
        text = skill_md.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return False
    return 'qclaw' in text.lower()


def normalize_model(model_value, fallback='unknown'):
    if isinstance(model_value, str) and model_value:
        return model_value
    if isinstance(model_value, dict):
        return model_value.get('primary') or model_value.get('id') or fallback
    return fallback


def provider_label(provider_id: str, provider_cfg: dict | None = None) -> str:
    if provider_cfg:
        custom = str(provider_cfg.get('label') or provider_cfg.get('name') or '').strip()
        if custom:
            return custom
    if provider_id in PROVIDER_LABELS:
        return PROVIDER_LABELS[provider_id]
    return provider_id.replace('-', ' ').title()


def full_model_id(provider_id: str, model_id: str) -> str:
    if '/' in model_id:
        return model_id
    return f'{provider_id}/{model_id}'


def human_model_label(model_id: str) -> str:
    raw = model_id.split('/')[-1]
    return raw.replace('-', ' ').replace('_', ' ').strip() or model_id


def build_known_models(cfg: dict) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()

    def add_model(model_id: str, label: str | None = None, provider: str | None = None):
        if not model_id or model_id in seen:
            return
        provider_id = provider or (model_id.split('/', 1)[0] if '/' in model_id else 'unknown')
        result.append({
            'id': model_id,
            'label': label or human_model_label(model_id),
            'provider': provider_label(provider_id, providers.get(provider_id, {})),
        })
        seen.add(model_id)

    providers = cfg.get('models', {}).get('providers', {})
    for provider_id, provider_cfg in providers.items():
        for model in provider_cfg.get('models', []) or []:
            model_id = full_model_id(provider_id, str(model.get('id', '')).strip())
            add_model(model_id, model.get('name') or model.get('label'), provider_id)

    defaults_models = cfg.get('agents', {}).get('defaults', {}).get('models', {}) or {}
    for model_id, meta in defaults_models.items():
        add_model(
            model_id,
            (meta or {}).get('label') or (meta or {}).get('alias'),
            model_id.split('/', 1)[0] if '/' in model_id else None,
        )

    default_primary = normalize_model(cfg.get('agents', {}).get('defaults', {}).get('model', {}), '')
    if default_primary:
        add_model(default_primary)

    for agent in cfg.get('agents', {}).get('list', []) or []:
        model_id = normalize_model(agent.get('model', ''), '')
        if model_id:
            add_model(model_id)

    return result


def get_skills(workspace: str):
    skills_dir = pathlib.Path(workspace) / 'skills'
    skills = []
    try:
        if skills_dir.exists():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir():
                    if d.name in _WORKSPACE_OBSOLETE_SKILLS:
                        continue
                    if _skill_contains_legacy_qclaw(d):
                        continue
                    md = d / 'SKILL.md'
                    desc = ''
                    if md.exists():
                        try:
                            for line in md.read_text(encoding='utf-8', errors='ignore').splitlines():
                                line = line.strip()
                                if line and not line.startswith('#') and not line.startswith('---'):
                                    desc = line[:100]
                                    break
                        except Exception:
                            desc = '(读取失败)'
                    skills.append({'name': d.name, 'path': str(md), 'exists': md.exists(), 'description': desc})
    except PermissionError as e:
        log.warning(f'Skills 目录访问受限: {e}')
    return skills


def main():
    cfg = {}
    try:
        cfg = json.loads(OPENCLAW_CFG.read_text())
    except Exception as e:
        log.warning(f'cannot read openclaw.json: {e}')
        return

    agents_cfg = cfg.get('agents', {})
    default_model = normalize_model(agents_cfg.get('defaults', {}).get('model', {}), 'unknown')
    agents_list = agents_cfg.get('list', [])

    result = []
    seen_ids = set()
    seen_canonical_ids = set()
    for ag in agents_list:
        ag_id = ag.get('id', '')
        if ag_id not in ID_LABEL:
            continue
        meta = ID_LABEL[ag_id]
        workspace = ag.get('workspace') or str(workspace_dir_for(ag_id) or (openclaw_home() / f'workspace-{ag_id}'))
        result.append({
            'id': ag_id,
            'label': meta['label'], 'role': meta['role'], 'duty': meta['duty'], 'emoji': meta['emoji'],
            'model': normalize_model(ag.get('model', default_model), default_model),
            'defaultModel': default_model,
            'workspace': workspace,
            'skills': get_skills(workspace),
            'allowAgents': ag.get('subagents', {}).get('allowAgents', []),
        })
        seen_ids.add(ag_id)
        seen_canonical_ids.add(canonical_agent_id(ag_id))

    # 补充不在 openclaw.json agents list 中的 agent
    EXTRA_AGENTS = {
        'chief_of_staff':   {'model': default_model, 'workspace': str(workspace_dir_for('chief_of_staff') or canonical_workspace_dir()),
                    'allowAgents': ['planning']},
        'people_ops': {'model': default_model, 'workspace': str(workspace_dir_for('people_ops') or canonical_workspace_dir()),
                    'allowAgents': ['delivery_ops']},
    }
    for ag_id, extra in EXTRA_AGENTS.items():
        if ag_id in seen_ids or ag_id not in ID_LABEL:
            continue
        if canonical_agent_id(ag_id) in seen_canonical_ids:
            continue
        meta = ID_LABEL[ag_id]
        result.append({
            'id': ag_id,
            'label': meta['label'], 'role': meta['role'], 'duty': meta['duty'], 'emoji': meta['emoji'],
            'model': extra['model'],
            'defaultModel': default_model,
            'workspace': extra['workspace'],
            'skills': get_skills(extra['workspace']),
            'allowAgents': extra['allowAgents'],
            'isDefaultModel': True,
        })
        seen_canonical_ids.add(canonical_agent_id(ag_id))

    payload = {
        'generatedAt': beijing_now().strftime('%Y-%m-%d %H:%M:%S'),
        'defaultModel': default_model,
        'knownModels': build_known_models(cfg),
        'agents': result,
    }
    DATA.mkdir(exist_ok=True)
    atomic_json_write(DATA / 'agent_config.json', payload)
    log.info(f'{len(result)} agents synced')

    # 自动部署 SOUL.md 到 workspace（如果项目里有更新）
    deploy_soul_files()
    # 同步 scripts/ 到各 workspace（保持 kanban_update.py 等最新）
    sync_scripts_to_workspaces()


# 项目 agents/ 目录名 → 运行时 agent_id 映射
_SOUL_DEPLOY_MAP = {
    'chief_of_staff': 'chief_of_staff',
    'planning': 'planning',
    'review_control': 'review_control',
    'delivery_ops': 'delivery_ops',
    'brand_content': 'brand_content',
    'business_analysis': 'business_analysis',
    'secops': 'secops',
    'compliance_test': 'compliance_test',
    'engineering': 'engineering',
    'people_ops': 'people_ops',
}

_WORKSPACE_RUNTIME_SCRIPTS = {
    'apply_model_changes.py',
    'browser_cli.py',
    'blocker_feedback.py',
    'blocker_utils.py',
    'delivery_guard.py',
    'delegate_agent.py',
    'extract_task_context.py',
    'file_lock.py',
    'incident_playbook.py',
    'intake_guard.py',
    'kanban_update.py',
    'plan_guard.py',
    'review_rubric.py',
    'review_readiness.py',
    'reset_agent_sessions.py',
    'refresh_live_data.py',
    'run_loop.sh',
    'runtime_paths.py',
    'task_ids.py',
    'chief_of_staff_council.py',
    'sync_agent_config.py',
    'sync_from_openclaw_runtime.py',
    'sync_officials_stats.py',
    'task_store_repair.py',
    'utils.py',
    'workbench_modes.py',
}

_WORKSPACE_OBSOLETE_SCRIPTS = set()
_WORKSPACE_OBSOLETE_SKILLS = {
    'zhipu-web-search',
}

_WORKSPACE_SHARED_FILES = {
    'incident-playbook.json',
    'review-rubric.json',
    'workbench-modes.json',
}

def _iter_runtime_scripts():
    """Only sync scripts that agents actually need inside workspace/scripts."""
    scripts_src = BASE / 'scripts'
    if not scripts_src.is_dir():
        return []
    return [
        src_file for src_file in sorted(scripts_src.iterdir())
        if src_file.name in _WORKSPACE_RUNTIME_SCRIPTS and src_file.is_file()
    ]


def _sync_scripts_into(ws_scripts: pathlib.Path, script_files: list[pathlib.Path]) -> int:
    synced = 0
    try:
        ws_scripts.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        log.warning(f'workspace scripts 目录写入受限: {ws_scripts} ({e})')
        return 0

    for src_file in script_files:
        dst_file = ws_scripts / src_file.name
        try:
            src_text = src_file.read_bytes()
        except Exception:
            continue
        try:
            dst_text = dst_file.read_bytes() if dst_file.exists() else b''
        except Exception:
            dst_text = b''
        if src_text == dst_text:
            continue
        try:
            dst_file.write_bytes(src_text)
            synced += 1
        except PermissionError as e:
            log.warning(f'script 同步受限: {dst_file} ({e})')
        except Exception as e:
            log.warning(f'script 同步失败: {dst_file} ({e})')
    for stale_name in sorted(_WORKSPACE_OBSOLETE_SCRIPTS):
        stale_path = ws_scripts / stale_name
        if not stale_path.exists():
            continue
        try:
            stale_path.unlink()
            synced += 1
        except PermissionError as e:
            log.warning(f'旧脚本清理受限: {stale_path} ({e})')
        except Exception as e:
            log.warning(f'旧脚本清理失败: {stale_path} ({e})')
    allowed_names = {src_file.name for src_file in script_files}
    for stale_path in sorted(ws_scripts.iterdir()):
        if not stale_path.is_file():
            continue
        if stale_path.name in allowed_names:
            continue
        try:
            stale_path.unlink()
            synced += 1
        except PermissionError as e:
            log.warning(f'非托管脚本清理受限: {stale_path} ({e})')
        except Exception as e:
            log.warning(f'非托管脚本清理失败: {stale_path} ({e})')
    return synced


def _iter_shared_files():
    shared_src = BASE / 'shared'
    if not shared_src.is_dir():
        return []
    return [
        src_file for src_file in sorted(shared_src.iterdir())
        if src_file.name in _WORKSPACE_SHARED_FILES and src_file.is_file()
    ]


def _sync_shared_into(ws_shared: pathlib.Path, shared_files: list[pathlib.Path]) -> int:
    synced = 0
    try:
        ws_shared.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        log.warning(f'workspace shared 目录写入受限: {ws_shared} ({e})')
        return 0

    for src_file in shared_files:
        dst_file = ws_shared / src_file.name
        try:
            src_bytes = src_file.read_bytes()
        except Exception:
            continue
        try:
            dst_bytes = dst_file.read_bytes() if dst_file.exists() else b''
        except Exception:
            dst_bytes = b''
        if src_bytes == dst_bytes:
            continue
        try:
            dst_file.write_bytes(src_bytes)
            synced += 1
        except PermissionError as e:
            log.warning(f'shared 配置同步受限: {dst_file} ({e})')
        except Exception as e:
            log.warning(f'shared 配置同步失败: {dst_file} ({e})')
    return synced


def _iter_builtin_skills():
    skills_src = BASE / 'skills'
    if not skills_src.is_dir():
        return []
    result = []
    for src_dir in sorted(skills_src.iterdir()):
        if not src_dir.is_dir():
            continue
        if src_dir.name.startswith('.'):
            continue
        if not (src_dir / 'SKILL.md').exists():
            continue
        if _skill_contains_legacy_qclaw(src_dir):
            continue
        result.append(src_dir)
    return result


def _sync_skill_dir(dst_dir: pathlib.Path, src_dir: pathlib.Path) -> int:
    synced = 0
    try:
        dst_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        log.warning(f'workspace skills 目录写入受限: {dst_dir} ({e})')
        return 0

    for src_path in sorted(src_dir.rglob('*')):
        rel_path = src_path.relative_to(src_dir)
        dst_path = dst_dir / rel_path
        try:
            if src_path.is_dir():
                dst_path.mkdir(parents=True, exist_ok=True)
                continue
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            src_bytes = src_path.read_bytes()
            try:
                dst_bytes = dst_path.read_bytes() if dst_path.exists() else b''
            except Exception:
                dst_bytes = b''
            if src_bytes == dst_bytes:
                continue
            dst_path.write_bytes(src_bytes)
            synced += 1
        except PermissionError as e:
            log.warning(f'skill 同步受限: {dst_path} ({e})')
        except Exception as e:
            log.warning(f'skill 同步失败: {dst_path} ({e})')
    return synced


def _dirs_match(src_dir: pathlib.Path, dst_dir: pathlib.Path) -> bool:
    if not src_dir.is_dir() or not dst_dir.is_dir():
        return False
    cmp = filecmp.dircmp(src_dir, dst_dir)
    if cmp.left_only or cmp.right_only or cmp.funny_files:
        return False
    matches, mismatch, errors = filecmp.cmpfiles(src_dir, dst_dir, cmp.common_files, shallow=False)
    if mismatch or errors:
        return False
    for common_dir in cmp.common_dirs:
        if not _dirs_match(src_dir / common_dir, dst_dir / common_dir):
            return False
    return True


def _cleanup_builtin_skill_copies(ws_skills: pathlib.Path, builtin_skill_dirs: list[pathlib.Path]) -> int:
    removed = 0
    if not ws_skills.exists():
        return 0
    builtin_by_name = {skill_dir.name: skill_dir for skill_dir in builtin_skill_dirs}
    for skill_dir in sorted(ws_skills.iterdir()):
        if not skill_dir.is_dir():
            continue
        if skill_dir.name in _WORKSPACE_OBSOLETE_SKILLS:
            try:
                shutil.rmtree(skill_dir)
                removed += 1
            except PermissionError as e:
                log.warning(f'废弃 skill 清理受限: {skill_dir} ({e})')
            except Exception as e:
                log.warning(f'废弃 skill 清理失败: {skill_dir} ({e})')
            continue
        src_dir = builtin_by_name.get(skill_dir.name)
        if src_dir is None:
            continue
        if (skill_dir / '.source.json').exists():
            continue
        try:
            if not _dirs_match(src_dir, skill_dir):
                continue
            shutil.rmtree(skill_dir)
            removed += 1
        except PermissionError as e:
            log.warning(f'内置 skill 清理受限: {skill_dir} ({e})')
        except Exception as e:
            log.warning(f'内置 skill 清理失败: {skill_dir} ({e})')
    return removed

def sync_scripts_to_workspaces():
    """将项目 scripts/shared 同步到各 agent workspace，并清理默认下发的内置 skills。"""
    script_files = _iter_runtime_scripts()
    shared_files = _iter_shared_files()
    builtin_skill_dirs = _iter_builtin_skills()
    if not script_files and not shared_files and not builtin_skill_dirs:
        return
    synced = 0
    removed_skills = 0
    seen_workspaces: set[str] = set()

    def _handle_workspace(workspace: pathlib.Path | None):
        nonlocal synced, removed_skills
        if not workspace:
            return
        key = str(workspace.resolve()) if workspace.exists() else str(workspace)
        if key in seen_workspaces:
            return
        seen_workspaces.add(key)
        ws_scripts = workspace / 'scripts'
        synced += _sync_scripts_into(ws_scripts, script_files)
        ws_shared = workspace / 'shared'
        synced += _sync_shared_into(ws_shared, shared_files)
        ws_skills = workspace / 'skills'
        removed_skills += _cleanup_builtin_skill_copies(ws_skills, builtin_skill_dirs)

    for proj_name, runtime_id in _SOUL_DEPLOY_MAP.items():
        _handle_workspace(workspace_dir_for(runtime_id))
    if synced:
        log.info(f'{synced} runtime files synced to workspaces')
    if removed_skills:
        log.info(f'{removed_skills} builtin skills removed from workspaces')


def _sync_text_file(dst: pathlib.Path, src_text: str) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        dst_text = dst.read_text(encoding='utf-8', errors='ignore')
    except FileNotFoundError:
        dst_text = ''
    if src_text == dst_text:
        return False
    dst.write_text(src_text, encoding='utf-8')
    return True

def deploy_soul_files():
    """将项目 agents/xxx/SOUL.md 部署到 OpenClaw runtime 的 workspace / agents 目录。"""
    agents_dir = BASE / 'agents'
    deployed = 0
    for proj_name, runtime_id in _SOUL_DEPLOY_MAP.items():
        src = agents_dir / proj_name / 'SOUL.md'
        if not src.exists():
            continue
        src_text = src.read_text(encoding='utf-8', errors='ignore')

        runtime_workspace = workspace_dir_for(runtime_id)
        targets = [
            runtime_workspace / 'SOUL.md' if runtime_workspace else None,
            agent_dir(runtime_id) / 'SOUL.md',
        ]

        for dst in targets:
            if dst is None:
                continue
            try:
                if _sync_text_file(dst, src_text):
                    deployed += 1
            except PermissionError as e:
                log.warning(f'SOUL.md 同步受限: {dst} ({e})')
            except Exception as e:
                log.warning(f'SOUL.md 同步失败: {dst} ({e})')
        # 确保 sessions 目录存在
        sess_dir = agent_dir(runtime_id) / 'sessions'
        sess_dir.mkdir(parents=True, exist_ok=True)
    if deployed:
        log.info(f'{deployed} SOUL.md files deployed')


if __name__ == '__main__':
    main()

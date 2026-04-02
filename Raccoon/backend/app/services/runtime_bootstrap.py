from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import importlib.util
from datetime import datetime
from pathlib import Path

from ..config import get_settings


SETTINGS = get_settings()

if os.environ.get("OPENCLAW_PROJECT_ROOT", "").strip():
    ROOT = Path(os.environ["OPENCLAW_PROJECT_ROOT"]).expanduser()
elif getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).parents[4]

OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw"))).expanduser()
OPENCLAW_CFG = OPENCLAW_HOME / "openclaw.json"
AGENT_REGISTRY_PATH = ROOT / "shared" / "agent-registry.json"
DEFAULT_MODEL_PRIMARY = "openai-codex/gpt-5.4"
DEFAULT_MODEL_CONFIG = {"primary": DEFAULT_MODEL_PRIMARY}

RACCOONCLAW_AGENTS = [
    {"id": "chief_of_staff", "allowAgents": ["planning"]},
    {"id": "planning", "allowAgents": ["review_control", "delivery_ops"]},
    {"id": "review_control", "allowAgents": ["delivery_ops", "planning"]},
    {"id": "delivery_ops", "allowAgents": ["planning", "review_control", "business_analysis", "brand_content", "secops", "compliance_test", "engineering", "people_ops"]},
    {"id": "business_analysis", "allowAgents": ["delivery_ops"]},
    {"id": "brand_content", "allowAgents": ["delivery_ops"]},
    {"id": "secops", "allowAgents": ["delivery_ops"]},
    {"id": "compliance_test", "allowAgents": ["delivery_ops"]},
    {"id": "engineering", "allowAgents": ["delivery_ops"]},
    {"id": "people_ops", "allowAgents": ["delivery_ops"]},
]

SOUL_DEPLOY_MAP = {item["id"]: item["id"] for item in RACCOONCLAW_AGENTS}

LEGACY_RUNTIME_IDS: tuple[str, ...] = ()

WORKSPACE_RUNTIME_SCRIPTS = {
    "blocker_feedback.py",
    "blocker_utils.py",
    "delivery_guard.py",
    "delegate_agent.py",
    "extract_task_context.py",
    "file_lock.py",
    "incident_playbook.py",
    "kanban_update.py",
    "intake_guard.py",
    "plan_guard.py",
    "refresh_live_data.py",
    "reset_agent_sessions.py",
    "review_readiness.py",
    "review_rubric.py",
    "runtime_paths.py",
    "task_ids.py",
    "sync_agent_config.py",
    "sync_from_openclaw_runtime.py",
    "task_store_repair.py",
    "chief_of_staff_council.py",
    "utils.py",
    "workbench_modes.py",
}

WORKSPACE_SHARED_FILES = {
    "incident-playbook.json",
    "review-rubric.json",
    "workbench-modes.json",
    "agent-registry.json",
    "workflow-config.json",
}

WORKSPACE_SHARED_SKILLS: set[str] = set()

REQUIRED_WORKBENCH_DATA_FILES = {
    "agent_config.json",
    "live_status.json",
    "officials_stats.json",
    "sync_status.json",
    "tasks_source.json",
}

COMPAT_AGENT_FAMILIES = {item["id"]: (item["id"],) for item in RACCOONCLAW_AGENTS}

USER_FACING_AGENT_LABELS = {
    "chief_of_staff": "总裁办",
    "planning": "产品规划部",
    "review_control": "评审质控部",
    "delivery_ops": "交付运营部",
    "brand_content": "品牌内容部",
    "business_analysis": "经营分析部",
    "secops": "安全运维部",
    "compliance_test": "合规测试部",
    "engineering": "工程研发部",
    "people_ops": "人力组织部",
}

AGENTS_MD_TEXT = """# AGENTS.md · 工作协议

1. 接到任务先回复"已收到需求"。
2. 输出必须包含：任务ID、结果、证据/文件路径、阻塞项。
3. 需要协作时，回复交付运营部请求转派，不跨团队直连。
4. 涉及删除/外发动作必须明确标注并等待批准。
"""

DATA_FILE_DEFAULTS: dict[str, object] = {
    "tasks_source.json": [],
    "live_status.json": {
        "tasks": [],
        "syncStatus": {
            "ok": True,
            "source": "raccoonclaw_bootstrap",
            "detail": "Bootstrap completed. Waiting for first runtime sync.",
            "checkedAt": "",
        },
        "health": {
            "syncOk": True,
        },
    },
    "agent_config.json": {
        "generatedAt": "",
        "defaultModel": "unknown",
        "knownModels": [],
        "agents": [],
    },
    "officials_stats.json": {"officials": []},
    "model_change_log.json": [],
    "last_model_change_result.json": {},
    "pending_model_changes.json": [],
    "sync_status.json": {
        "ok": True,
            "source": "raccoonclaw_bootstrap",
        "detail": "Bootstrap completed. Waiting for first runtime sync.",
        "checkedAt": "",
    },
    "chat_sessions.json": {
        "sessions": [],
    },
}


def _resolve_openclaw_bin() -> str | None:
    explicit = os.environ.get("OPENCLAW_BIN", "").strip()
    if explicit and Path(explicit).is_file():
        return explicit
    detected = shutil.which(SETTINGS.openclaw_bin) or shutil.which("openclaw")
    return detected


def _subprocess_path_env() -> str:
    entries: list[str] = []
    existing = os.environ.get("PATH", "").strip()
    if existing:
        entries.extend(part for part in existing.split(os.pathsep) if part)
    for candidate in (
        "/opt/homebrew/bin",
        "/opt/homebrew/opt/node@22/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ):
        if candidate not in entries:
            entries.append(candidate)
    return os.pathsep.join(entries)


def _openclaw_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = _subprocess_path_env()
    # The OpenClaw CLI already resolves its config under ~/.openclaw by default.
    # Passing OPENCLAW_HOME=~/.openclaw into subprocesses can make some builds
    # resolve nested paths like ~/.openclaw/.openclaw/openclaw.json.
    env.pop("OPENCLAW_HOME", None)
    env.pop("OPENCLAW_WORKSPACE", None)
    return env


def _run_openclaw(args: list[str], timeout: int = 120) -> tuple[bool, str]:
    binary = _resolve_openclaw_bin()
    if not binary:
        return False, "openclaw CLI not found"
    try:
        completed = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_openclaw_subprocess_env(),
        )
    except Exception as exc:
        return False, str(exc)

    output = "\n".join([part for part in [completed.stdout.strip(), completed.stderr.strip()] if part]).strip()
    return completed.returncode == 0, output


def _runtime_agent_ids() -> list[str]:
    ok, output = _run_openclaw(["agents", "list"], timeout=20)
    if not ok or not output:
        return []
    agent_ids: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.lower().startswith("id ") or line == "Agents:":
            continue
        if not line.startswith("- "):
            continue
        candidate = line[2:].split()[0].strip()
        if candidate and candidate not in agent_ids:
            agent_ids.append(candidate)
    return agent_ids


def _chief_of_staff_runtime_ready(agent_ids: list[str]) -> bool:
    return "chief_of_staff" in agent_ids


def _agent_auth_profile_path(agent_id: str) -> Path:
    return OPENCLAW_HOME / "agents" / agent_id / "agent" / "auth-profiles.json"


def _preferred_chief_of_staff_agent_id(agent_ids: list[str]) -> str:
    for candidate in ("chief_of_staff",):
        if candidate in agent_ids:
            return candidate
    for candidate in ("chief_of_staff",):
        if _agent_runtime_dir(candidate).exists():
            return candidate
    return "chief_of_staff"


def _chief_of_staff_auth_ready(agent_ids: list[str]) -> bool:
    preferred = _preferred_chief_of_staff_agent_id(agent_ids)
    profile = _agent_auth_profile_path(preferred)
    return profile.exists() and profile.stat().st_size > 2


def _agent_candidates(agent_id: str) -> tuple[str, ...]:
    return COMPAT_AGENT_FAMILIES.get(agent_id, (agent_id,))


def _resolve_agent_entry(agent_map: dict[str, dict], agent_id: str) -> tuple[str | None, dict | None]:
    for candidate in _agent_candidates(agent_id):
        entry = agent_map.get(candidate)
        if isinstance(entry, dict):
            return candidate, entry
    return None, None


def _resolve_workspace_path(agent_map: dict[str, dict], agent_id: str) -> Path:
    resolved_id, entry = _resolve_agent_entry(agent_map, agent_id)
    raw_workspace = ""
    if isinstance(entry, dict):
        raw_workspace = str(entry.get("workspace") or "").strip()
    if raw_workspace:
        return Path(raw_workspace).expanduser()
    if resolved_id:
        return _workspace(resolved_id)
    return _workspace(agent_id)


def _workbench_data_dir(agent_map: dict[str, dict] | None = None) -> Path:
    agent_map = agent_map or {}
    candidates = [
        _resolve_workspace_path(agent_map, "chief_of_staff") / "data",
        _workspace("chief_of_staff") / "data",
    ]
    for path in candidates:
        if any((path / name).exists() for name in REQUIRED_WORKBENCH_DATA_FILES):
            path.mkdir(parents=True, exist_ok=True)
            return path
    fallback = candidates[0]
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _embedded_script_module(module_name: str):
    scripts_root = ROOT / "scripts"
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    spec = importlib.util.spec_from_file_location(
        f"edictclaw_{module_name}",
        scripts_root / f"{module_name}.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载脚本模块: {module_name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_embedded_script(module_name: str) -> None:
    module = _embedded_script_module(module_name)
    entry = getattr(module, "main", None)
    if not callable(entry):
        raise RuntimeError(f"{module_name}.py 缺少 main()")
    entry()


def _gateway_token_synced(cfg: dict | None = None) -> bool:
    if cfg is None:
        cfg = _read_json(OPENCLAW_CFG, {})
    gateway_cfg = (cfg or {}).get("gateway") or {}
    if not isinstance(gateway_cfg, dict):
        return True
    auth_cfg = gateway_cfg.get("auth") or {}
    remote_cfg = gateway_cfg.get("remote") or {}
    if not isinstance(auth_cfg, dict):
        auth_cfg = {}
    if not isinstance(remote_cfg, dict):
        remote_cfg = {}
    auth_token = str(auth_cfg.get("token") or "").strip()
    remote_token = str(remote_cfg.get("token") or "").strip()
    if not auth_token:
        return True
    return auth_token == remote_token


def _sync_gateway_remote_token(cfg: dict | None = None) -> tuple[dict, bool]:
    if cfg is None:
        cfg = _read_json(OPENCLAW_CFG, {})
    gateway_cfg = cfg.setdefault("gateway", {})
    if not isinstance(gateway_cfg, dict):
        gateway_cfg = {}
        cfg["gateway"] = gateway_cfg
    auth_cfg = gateway_cfg.setdefault("auth", {})
    if not isinstance(auth_cfg, dict):
        auth_cfg = {}
        gateway_cfg["auth"] = auth_cfg
    remote_cfg = gateway_cfg.setdefault("remote", {})
    if not isinstance(remote_cfg, dict):
        remote_cfg = {}
        gateway_cfg["remote"] = remote_cfg
    auth_token = str(auth_cfg.get("token") or "").strip()
    remote_token = str(remote_cfg.get("token") or "").strip()
    if not auth_token:
        return cfg, False
    if remote_token == auth_token:
        return cfg, False
    remote_cfg["token"] = auth_token
    return cfg, True


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _sanitize_user_facing_text(text: str) -> str:
    sanitized = str(text or "")
    sanitized = re.sub(
        r'Unknown agent id "([^"]+)"',
        lambda match: f'未知{USER_FACING_AGENT_LABELS.get(match.group(1), "Agent")} Agent',
        sanitized,
    )
    sanitized = re.sub(
        r'Auth store:\s+[^\n"]+auth-profiles\.json',
        'Auth store: 当前总裁办认证文件',
        sanitized,
    )
    sanitized = re.sub(
        r'\(agentDir:\s+[^)]+\)',
        '(agentDir: 当前总裁办 Agent 目录)',
        sanitized,
    )
    sanitized = re.sub(
        r'/agents/chief_of_staff/agent/auth-profiles\.json',
        '/agents/总裁办/agent/auth-profiles.json',
        sanitized,
    )
    return sanitized


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy_file(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    src_bytes = src.read_bytes()
    try:
        if dst.exists() and dst.read_bytes() == src_bytes:
            return False
    except Exception:
        pass
    dst.write_bytes(src_bytes)
    return True


def _copy_tree(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    copied = 0
    for src_path in src.rglob("*"):
        rel = src_path.relative_to(src)
        dst_path = dst / rel
        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            continue
        if _copy_file(src_path, dst_path):
            copied += 1
    return copied


def _managed_backup_paths() -> list[tuple[Path, str]]:
    paths: list[tuple[Path, str]] = []
    seen: set[str] = set()

    for agent_id in _required_agent_ids():
        for src, backup_name in (
            (_workspace(agent_id), _workspace(agent_id).name),
            (_agent_runtime_dir(agent_id), f"agent-{agent_id}"),
        ):
            key = str(src)
            if key not in seen:
                seen.add(key)
                paths.append((src, backup_name))

    for legacy_id in LEGACY_RUNTIME_IDS:
        for src, backup_name in (
            (OPENCLAW_HOME / f"workspace-{legacy_id}", f"legacy-workspace-{legacy_id}"),
            (_agent_runtime_dir(legacy_id), f"legacy-agent-{legacy_id}"),
        ):
            key = str(src)
            if key not in seen:
                seen.add(key)
                paths.append((src, backup_name))

    return paths


def _backup_path(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _move_or_merge_path(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    try:
        if src.resolve() == dst.resolve():
            return False
    except Exception:
        pass

    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.move(str(src), str(dst))
        return True

    if src.is_dir() and dst.is_dir():
        _copy_tree(src, dst)
        shutil.rmtree(src)
        return True

    if src.is_file() and dst.is_file():
        changed = _copy_file(src, dst)
        src.unlink(missing_ok=True)
        return changed

    if src.is_file() and dst.is_dir():
        target = dst / src.name
        changed = _copy_file(src, target)
        src.unlink(missing_ok=True)
        return changed

    return False


def _cleanup_legacy_runtime_layout() -> dict[str, int]:
    workspace_removed = 0
    agent_removed = 0

    for legacy_id in LEGACY_RUNTIME_IDS:
        legacy_workspace = OPENCLAW_HOME / f"workspace-{legacy_id}"
        if legacy_workspace.exists():
            shutil.rmtree(legacy_workspace, ignore_errors=True)
            workspace_removed += 1
        legacy_agent = _agent_runtime_dir(legacy_id)
        if legacy_agent.exists():
            shutil.rmtree(legacy_agent, ignore_errors=True)
            agent_removed += 1

    return {
        "workspaces": workspace_removed,
        "agents": agent_removed,
    }


def _resource_dir(name: str) -> Path:
    return ROOT / name


def _workspace(agent_id: str) -> Path:
    return OPENCLAW_HOME / f"workspace-{agent_id}"


def _agent_runtime_dir(agent_id: str) -> Path:
    return OPENCLAW_HOME / "agents" / agent_id


def _required_agent_ids() -> list[str]:
    return [item["id"] for item in RACCOONCLAW_AGENTS]


def _bootstrap_ready_details() -> dict:
    cli_bin = _resolve_openclaw_bin()
    runtime_agent_ids = _runtime_agent_ids() if cli_bin else []
    cfg = _read_json(OPENCLAW_CFG, {})
    agents_list = (cfg.get("agents") or {}).get("list") or []
    agent_map = {str(item.get("id")): item for item in agents_list if isinstance(item, dict)}
    missing_agents = [
        agent_id for agent_id in _required_agent_ids()
        if _resolve_agent_entry(agent_map, agent_id)[1] is None
    ]

    missing_workspaces = []
    missing_soul = []
    for agent_id in _required_agent_ids():
        workspace = _resolve_workspace_path(agent_map, agent_id)
        if not workspace.exists():
            missing_workspaces.append(agent_id)
        if not (workspace / "SOUL.md").exists():
            missing_soul.append(agent_id)

    workbench_scripts = _resolve_workspace_path(agent_map, "chief_of_staff") / "scripts"
    missing_scripts = sorted(
        name for name in ("kanban_update.py", "delegate_agent.py", "chief_of_staff_council.py")
        if not (workbench_scripts / name).exists()
    )
    workbench_skills = _resolve_workspace_path(agent_map, "chief_of_staff") / "skills"
    missing_skills = sorted(
        name for name in WORKSPACE_SHARED_SKILLS
        if not (workbench_skills / name).exists()
    )
    workbench_data = _workbench_data_dir(agent_map)
    missing_data_files = sorted(
        name for name in REQUIRED_WORKBENCH_DATA_FILES
        if not (workbench_data / name).exists()
    )
    agent_config = _read_json(workbench_data / "agent_config.json", {})
    officials_stats = _read_json(workbench_data / "officials_stats.json", {})
    live_status = _read_json(workbench_data / "live_status.json", {})
    chat_store = _read_json(workbench_data / "chat_sessions.json", {})
    legacy_runtime_ids: list[str] = []
    legacy_config_ids: list[str] = []

    return {
        "cliInstalled": bool(cli_bin),
        "cliPath": cli_bin or "",
        "runtimeAgentIds": runtime_agent_ids,
        "chiefOfStaffRuntimeReady": _chief_of_staff_runtime_ready(runtime_agent_ids),
        "preferredChiefOfStaffAgentId": _preferred_chief_of_staff_agent_id(runtime_agent_ids),
        "chiefOfStaffAuthReady": _chief_of_staff_auth_ready(runtime_agent_ids),
        "gatewayTokenSynced": _gateway_token_synced(cfg),
        "openclawHome": str(OPENCLAW_HOME),
        "configExists": OPENCLAW_CFG.exists(),
        "missingAgents": missing_agents,
        "missingWorkspaces": missing_workspaces,
        "missingSoul": missing_soul,
        "missingScripts": missing_scripts,
        "missingSkills": missing_skills,
        "missingDataFiles": missing_data_files,
        "legacyRuntimeIds": legacy_runtime_ids,
        "legacyMainWorkspace": False,
        "legacyConfigIds": legacy_config_ids,
        "legacyLayoutDetected": False,
        "agentConfigReady": bool((agent_config or {}).get("agents")),
        "officialsStatsReady": bool((officials_stats or {}).get("officials")),
        "liveStatusReady": isinstance((live_status or {}).get("tasks"), list),
        "chatStoreReady": isinstance((chat_store or {}).get("sessions"), list),
    }


def _gateway_status_details() -> dict:
    cli_bin = _resolve_openclaw_bin()
    if not cli_bin:
        return {
            "gatewayStatusOk": False,
            "gatewayReachable": False,
            "gatewayDashboardUrl": "",
            "gatewaySummary": "未检测到 OpenClaw CLI",
            "gatewayDetail": "请先安装 OpenClaw CLI，再检查 gateway 状态。",
            "gatewayRecommendedAction": "install_cli",
            "gatewayOutput": "",
        }

    ok, output = _run_openclaw(["gateway", "status"], timeout=20)
    dashboard_url = ""
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("Dashboard: "):
            dashboard_url = line.removeprefix("Dashboard: ").strip()
            break

    lower_output = output.lower()
    reachable_hint = ok or "rpc probe:" in lower_output or "dashboard:" in lower_output
    recommended_action = "restart_gateway" if reachable_hint else "install_gateway"
    if ok:
        summary = "OpenClaw runtime 和 gateway 已就绪"
        detail = "可以直接进入工作台。"
    elif "node: no such file or directory" in lower_output:
        summary = "OpenClaw CLI 可用，但本机缺少 Node.js 运行环境"
        detail = "Gateway 依赖 Node.js。请先安装 Node.js，再重新检查。"
        recommended_action = "install_node"
    elif "gateway token missing" in lower_output or "unauthorized" in lower_output:
        summary = "Gateway token 未对齐"
        detail = "当前 gateway 鉴权配置不一致。需要同步 gateway.remote.token 与 gateway.auth.token 后重启 gateway。"
        recommended_action = "bootstrap"
    elif recommended_action == "restart_gateway":
        summary = "OpenClaw CLI 可用，但 gateway 状态异常"
        detail = "建议先尝试“重启 Gateway”，如果仍失败，再执行 Doctor 修复。"
    else:
        summary = "OpenClaw CLI 可用，但尚未安装或启动 gateway"
        detail = "建议先执行“安装 Gateway”，再重新检查。"

    return {
        "gatewayStatusOk": ok,
        "gatewayReachable": reachable_hint,
        "gatewayDashboardUrl": dashboard_url,
        "gatewaySummary": summary,
        "gatewayDetail": detail,
        "gatewayRecommendedAction": recommended_action,
        "gatewayOutput": output,
    }


def get_bootstrap_status() -> dict:
    details = _bootstrap_ready_details()
    if details.get("cliInstalled") and details.get("configExists"):
        changed = False
        cfg = _read_json(OPENCLAW_CFG, {})

        if not details.get("chiefOfStaffAuthReady"):
            auth_sync = _seed_auth_profiles()
            changed = changed or bool(auth_sync.get("copied"))

        if not details.get("gatewayTokenSynced"):
            cfg, token_synced = _sync_gateway_remote_token(cfg)
            if token_synced:
                _write_json(OPENCLAW_CFG, cfg)
                _run_openclaw(["gateway", "restart"], timeout=90)
                changed = True

        needs_runtime_data = bool(details.get("missingDataFiles")) or not all(
            [
                details.get("agentConfigReady"),
                details.get("officialsStatsReady"),
                details.get("liveStatusReady"),
                details.get("chatStoreReady"),
            ]
        )
        if needs_runtime_data:
            _initialize_data(cfg)
            _refresh_runtime_data()
            changed = True

        if changed:
            details = _bootstrap_ready_details()

    if not details["cliInstalled"]:
        return {
            "ok": False,
            "ready": False,
            "recommendedAction": "install_cli",
            "summary": "未检测到 OpenClaw CLI",
            "detail": "请先安装 OpenClaw CLI，安装后再初始化 RaccoonClaw-OSS 组织配置。",
            **details,
        }

    if not details["configExists"]:
        return {
            "ok": True,
            "ready": False,
            "recommendedAction": "init_openclaw",
            "summary": "OpenClaw 尚未初始化",
            "detail": "当前机器已安装 OpenClaw CLI，但还没有 openclaw.json。需要先初始化 OpenClaw，再导入 RaccoonClaw-OSS 组织配置。",
            **details,
        }

    missing_total = sum(
        len(details[key])
        for key in (
            "missingAgents",
            "missingWorkspaces",
            "missingSoul",
            "missingScripts",
            "missingSkills",
            "missingDataFiles",
        )
    )
    if missing_total == 0 and not details["chiefOfStaffRuntimeReady"]:
        return {
            "ok": True,
            "ready": False,
            "recommendedAction": "bootstrap",
            "summary": "组织配置文件已存在，但总裁办 Agent 未注册到 OpenClaw 运行时",
            "detail": "当前 OpenClaw 运行时还没有可用的总裁办 Agent。需要重新导入组织配置并重启 Gateway。",
            **details,
        }
    if missing_total == 0 and not details["chiefOfStaffAuthReady"]:
        return {
            "ok": True,
            "ready": False,
            "recommendedAction": "bootstrap",
            "summary": "组织配置已导入，但总裁办认证未就绪",
            "detail": "当前总裁办运行时缺少认证文件。需要补齐认证配置后才能进入工作台。",
            **details,
        }
    if missing_total == 0 and not details["gatewayTokenSynced"]:
        return {
            "ok": True,
            "ready": False,
            "recommendedAction": "bootstrap",
            "summary": "组织配置已导入，但 Gateway token 未同步",
            "detail": "当前 gateway.remote.token 与 gateway.auth.token 不一致或缺失。需要修复配置并重启 Gateway 后才能进入工作台。",
            **details,
        }
    if missing_total == 0 and not details["agentConfigReady"]:
        return {
            "ok": True,
            "ready": False,
            "recommendedAction": "bootstrap",
            "summary": "组织配置已导入，但 Agent 配置尚未生成",
            "detail": "当前工作台还没有生成可用的 Agent 配置数据。需要重新执行组织配置导入。",
            **details,
        }
    if missing_total == 0 and not details["officialsStatsReady"]:
        return {
            "ok": True,
            "ready": False,
            "recommendedAction": "bootstrap",
            "summary": "组织配置已导入，但团队角色统计尚未生成",
            "detail": "当前工作台还没有生成团队角色统计。需要重新执行组织配置导入。",
            **details,
        }
    if missing_total == 0 and not details["liveStatusReady"]:
        return {
            "ok": True,
            "ready": False,
            "recommendedAction": "bootstrap",
            "summary": "组织配置已导入，但状态数据尚未生成",
            "detail": "当前工作台还没有生成状态监控所需数据。需要重新执行组织配置导入。",
            **details,
        }
    if missing_total == 0 and details.get("legacyLayoutDetected"):
        return {
            "ok": True,
            "ready": False,
            "recommendedAction": "bootstrap",
            "summary": "检测到非 canonical 运行时目录",
            "detail": "当前机器仍保留非 canonical 运行时目录或旧 agent 配置。需要重新执行组织配置导入并清理旧运行时。",
            **details,
        }
    if missing_total == 0:
        return {
            "ok": True,
            "ready": True,
            "recommendedAction": "none",
            "summary": "RaccoonClaw-OSS 组织配置已安装",
            "detail": "当前 OpenClaw 环境已经包含总裁办分流体系和所需 workspace 资源。",
            **details,
        }

    return {
        "ok": True,
        "ready": False,
        "recommendedAction": "bootstrap",
        "summary": "OpenClaw 已安装，但未导入 RaccoonClaw-OSS 组织配置",
        "detail": "需要把 agents、workflow、SOUL、scripts 和 skills 导入到当前 OpenClaw 环境。",
        **details,
    }


def get_desktop_startup_status() -> dict:
    bootstrap = get_bootstrap_status()
    gateway = _gateway_status_details()
    ready = bool(
        bootstrap.get("ready")
        and bootstrap.get("cliInstalled")
        and gateway.get("gatewayStatusOk")
    )

    if not bootstrap.get("cliInstalled"):
        summary = bootstrap.get("summary", "未检测到 OpenClaw CLI")
        detail = bootstrap.get("detail", "")
        recommended_action = "install_cli"
        status_output = ""
    elif not gateway.get("gatewayStatusOk"):
        summary = gateway.get("gatewaySummary", "Gateway 未就绪")
        detail = gateway.get("gatewayDetail", "")
        recommended_action = gateway.get("gatewayRecommendedAction", "install_gateway")
        status_output = gateway.get("gatewayOutput", "")
    elif not bootstrap.get("ready"):
        summary = bootstrap.get("summary", "组织配置未就绪")
        detail = bootstrap.get("detail", "")
        recommended_action = bootstrap.get("recommendedAction", "bootstrap")
        status_output = ""
    else:
        summary = "RaccoonClaw-OSS 已就绪"
        detail = "OpenClaw CLI、gateway 和组织配置都已通过检查，可以进入工作台。"
        recommended_action = "none"
        status_output = gateway.get("gatewayOutput", "")

    return {
        "ok": True,
        "ready": ready,
        "summary": summary,
        "detail": detail,
        "recommendedAction": recommended_action,
        "cliInstalled": bool(bootstrap.get("cliInstalled")),
        "cliPath": bootstrap.get("cliPath", ""),
        "gatewayStatusOk": bool(gateway.get("gatewayStatusOk")),
        "gatewayReachable": bool(gateway.get("gatewayReachable")),
        "gatewayDashboardUrl": gateway.get("gatewayDashboardUrl", ""),
        "statusOutput": status_output,
        "bootstrapReady": bool(bootstrap.get("ready")),
        "bootstrapSummary": bootstrap.get("summary", ""),
        "bootstrapDetail": bootstrap.get("detail", ""),
        "bootstrapRecommendedAction": bootstrap.get("recommendedAction", "bootstrap"),
        "runtimeAgentIds": bootstrap.get("runtimeAgentIds", []),
        "chiefOfStaffRuntimeReady": bool(bootstrap.get("chiefOfStaffRuntimeReady")),
        "configExists": bool(bootstrap.get("configExists")),
        "openclawHome": bootstrap.get("openclawHome", ""),
        "missingAgents": bootstrap.get("missingAgents", []),
        "missingWorkspaces": bootstrap.get("missingWorkspaces", []),
        "missingSoul": bootstrap.get("missingSoul", []),
        "missingScripts": bootstrap.get("missingScripts", []),
        "missingSkills": bootstrap.get("missingSkills", []),
        "missingDataFiles": bootstrap.get("missingDataFiles", []),
    }


def _ensure_openclaw_initialized() -> tuple[bool, str]:
    if OPENCLAW_CFG.exists():
        return True, ""
    ok, output = _run_openclaw(
        [
            "onboard",
            "--non-interactive",
            "--accept-risk",
            "--skip-channels",
            "--skip-skills",
            "--skip-search",
            "--skip-ui",
            "--skip-health",
            "--workspace",
            str(OPENCLAW_HOME / "workspace"),
        ],
        timeout=120,
    )
    if ok and OPENCLAW_CFG.exists():
        return True, output
    return False, output or "openclaw onboard failed"


def _backup_existing() -> Path:
    backup_dir = OPENCLAW_HOME / "backups" / f"edictclaw-bootstrap-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    if OPENCLAW_CFG.exists():
        shutil.copy2(OPENCLAW_CFG, backup_dir / "openclaw.json")

    for src, backup_name in _managed_backup_paths():
        _backup_path(src, backup_dir / backup_name)
    return backup_dir


def _merge_agents_config() -> dict:
    cfg = _read_json(OPENCLAW_CFG, {})
    gateway_cfg = cfg.setdefault("gateway", {})
    if isinstance(gateway_cfg, dict):
        auth_cfg = gateway_cfg.setdefault("auth", {})
        if not isinstance(auth_cfg, dict):
            auth_cfg = {}
            gateway_cfg["auth"] = auth_cfg
        remote_cfg = gateway_cfg.setdefault("remote", {})
        if not isinstance(remote_cfg, dict):
            remote_cfg = {}
            gateway_cfg["remote"] = remote_cfg
        token = str(auth_cfg.get("token") or remote_cfg.get("token") or "").strip()
        if token:
            auth_cfg.setdefault("mode", "token")
            auth_cfg["token"] = token
            remote_cfg["token"] = token

    agents_cfg = cfg.setdefault("agents", {})
    defaults = agents_cfg.setdefault("defaults", {})
    defaults["workspace"] = str(_workspace("chief_of_staff"))
    defaults["model"] = dict(DEFAULT_MODEL_CONFIG)
    defaults.setdefault("models", {})
    defaults["models"].setdefault(
        DEFAULT_MODEL_PRIMARY,
        {"label": "GPT-5.4", "provider": "openai-codex"},
    )
    defaults.setdefault("memorySearch", {"enabled": False})
    defaults.setdefault("compaction", {"mode": "safeguard"})
    defaults.setdefault("maxConcurrent", 4)
    defaults.setdefault("subagents", {"maxConcurrent": 8})

    tools_cfg = cfg.setdefault("tools", {})
    if not isinstance(tools_cfg, dict):
        tools_cfg = {}
        cfg["tools"] = tools_cfg
    tools_cfg["profile"] = "coding"

    existing_list = agents_cfg.get("list") or []
    managed_ids = set(_required_agent_ids())
    canonicalized: dict[str, dict] = {}

    for item in existing_list:
        if not isinstance(item, dict):
            continue
        raw_id = str(item.get("id") or "").strip()
        if not raw_id:
            continue
        canonical_id = raw_id
        if canonical_id not in managed_ids:
            continue
        current = canonicalized.get(canonical_id)
        if current is None:
            canonicalized[canonical_id] = dict(item)
            continue
        if raw_id == canonical_id and str(current.get("id") or "").strip() != canonical_id:
            merged_entry = dict(current)
            merged_entry.update(item)
            canonicalized[canonical_id] = merged_entry
            continue
        merged_entry = dict(current)
        for key, value in item.items():
            if key == "id":
                continue
            if key not in merged_entry or merged_entry[key] in ("", None, [], {}):
                merged_entry[key] = value
        canonicalized[canonical_id] = merged_entry

    merged = []
    seen = set()

    for spec in RACCOONCLAW_AGENTS:
        agent_id = spec["id"]
        entry = dict(canonicalized.get(agent_id) or {})
        entry["id"] = agent_id
        entry["workspace"] = str(_workspace(agent_id))
        entry["model"] = dict(DEFAULT_MODEL_CONFIG)
        entry["subagents"] = {"allowAgents": list(spec["allowAgents"])}
        merged.append(entry)
        seen.add(agent_id)

    for item in existing_list:
        if not isinstance(item, dict):
            continue
        agent_id = str(item.get("id") or "")
        canonical_id = agent_id
        if not agent_id or agent_id in seen or canonical_id in managed_ids:
            continue
        merged.append(item)

    agents_cfg["list"] = merged
    return cfg


def _seed_auth_profiles() -> dict[str, object]:
    source: Path | None = None
    seen: set[Path] = set()
    configured_ids = {
        str(item.get("id") or "").strip()
        for item in ((_read_json(OPENCLAW_CFG, {}).get("agents") or {}).get("list") or [])
        if isinstance(item, dict)
    }
    candidate_ids = ["chief_of_staff", *_required_agent_ids()]
    for agent_id in candidate_ids:
        path = _agent_auth_profile_path(agent_id)
        if path in seen:
            continue
        seen.add(path)
        if path.exists() and path.stat().st_size > 2:
            source = path
            break
    if source is None:
        for path in sorted((OPENCLAW_HOME / "agents").glob("*/agent/auth-profiles.json")):
            if path.exists() and path.stat().st_size > 2:
                source = path
                break

    if source is None:
        return {"source": "", "copied": 0}

    target_ids = set(["chief_of_staff", *_required_agent_ids()])

    copied = 0
    for agent_id in sorted(target_ids):
        dst = _agent_auth_profile_path(agent_id)
        copied += int(_copy_file(source, dst))
    return {"source": str(source), "copied": copied}


def _provision_workspaces() -> None:
    for agent_id in _required_agent_ids():
        workspace = _workspace(agent_id)
        for relative in ("skills", "scripts", "shared", "data"):
            (workspace / relative).mkdir(parents=True, exist_ok=True)
        _write_text(workspace / "AGENTS.md", AGENTS_MD_TEXT)
        (_agent_runtime_dir(agent_id) / "sessions").mkdir(parents=True, exist_ok=True)


def _deploy_soul_files() -> int:
    deployed = 0
    agents_dir = _resource_dir("agents")
    for source_dir, runtime_id in SOUL_DEPLOY_MAP.items():
        src = agents_dir / source_dir / "SOUL.md"
        if not src.exists():
            continue
        src_text = src.read_text(encoding="utf-8", errors="ignore")
        targets = [
            _workspace(runtime_id) / "SOUL.md",
            _agent_runtime_dir(runtime_id) / "SOUL.md",
        ]
        for dst in targets:
            before = dst.exists()
            _write_text(dst, src_text)
            if not before or dst.read_text(encoding="utf-8", errors="ignore") == src_text:
                deployed += 1
    return deployed


def _sync_runtime_assets() -> dict[str, int]:
    scripts_root = _resource_dir("scripts")
    shared_root = _resource_dir("shared")
    skills_root = _resource_dir("skills")
    script_count = 0
    shared_count = 0
    skill_count = 0

    for agent_id in _required_agent_ids():
        ws = _workspace(agent_id)
        for name in WORKSPACE_RUNTIME_SCRIPTS:
            script_count += int(_copy_file(scripts_root / name, ws / "scripts" / name))
        ws_scripts = ws / "scripts"
        if ws_scripts.exists():
            for stale in ws_scripts.iterdir():
                if not stale.is_file():
                    continue
                if stale.name in WORKSPACE_RUNTIME_SCRIPTS:
                    continue
                stale.unlink(missing_ok=True)
                script_count += 1
        for name in WORKSPACE_SHARED_FILES:
            shared_count += int(_copy_file(shared_root / name, ws / "shared" / name))
        for name in WORKSPACE_SHARED_SKILLS:
            skill_count += _copy_tree(skills_root / name, ws / "skills" / name)

    return {"scripts": script_count, "shared": shared_count, "skills": skill_count}


def _build_agent_config(cfg: dict) -> dict:
    registry = _read_json(AGENT_REGISTRY_PATH, [])
    registry_map = {item["id"]: item for item in registry if isinstance(item, dict) and item.get("id")}
    agents = []
    known_models: dict[str, dict] = {}

    default_model = (
        ((cfg.get("agents") or {}).get("defaults") or {}).get("model") or {}
    ).get("primary", "unknown")

    for item in ((cfg.get("agents") or {}).get("list") or []):
        if not isinstance(item, dict):
            continue
        agent_id = str(item.get("id") or "")
        if agent_id not in registry_map:
            continue
        meta = registry_map[agent_id]
        model = item.get("model") or default_model
        if isinstance(model, dict):
            model = model.get("primary") or model.get("id") or default_model
        model = str(model or default_model)
        known_models[model] = {
            "id": model,
            "label": model.split("/")[-1].replace("-", " "),
            "provider": model.split("/")[0] if "/" in model else "unknown",
        }
        workspace = Path(item.get("workspace") or _workspace(agent_id)).expanduser()
        skills_dir = workspace / "skills"
        skills = []
        if skills_dir.exists():
            for skill_dir in sorted(skills_dir.iterdir()):
                if skill_dir.is_dir():
                    skills.append({
                        "name": skill_dir.name,
                        "path": str(skill_dir / "SKILL.md"),
                        "exists": (skill_dir / "SKILL.md").exists(),
                        "description": "",
                    })
        agents.append({
            "id": agent_id,
            "label": meta.get("label", agent_id),
            "role": meta.get("displayRole", ""),
            "duty": meta.get("duty", ""),
            "emoji": meta.get("emoji", ""),
            "model": model,
            "defaultModel": default_model,
            "workspace": str(workspace),
            "skills": skills,
            "allowAgents": ((item.get("subagents") or {}).get("allowAgents") or []),
        })

    return {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "defaultModel": default_model,
        "knownModels": list(known_models.values()),
        "agents": agents,
    }


def _initialize_data(cfg: dict) -> None:
    agent_map = {
        str(item.get("id")): item
        for item in ((cfg.get("agents") or {}).get("list") or [])
        if isinstance(item, dict)
    }
    data_dir = _workbench_data_dir(agent_map)
    data_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for filename, default in DATA_FILE_DEFAULTS.items():
        path = data_dir / filename
        payload = default
        if filename == "agent_config.json":
            payload = _build_agent_config(cfg)
        elif filename in {"live_status.json", "sync_status.json"}:
            payload = json.loads(json.dumps(default))
            if isinstance(payload, dict):
                payload["checkedAt"] = timestamp
                sync_status = payload.get("syncStatus")
                if isinstance(sync_status, dict):
                    sync_status["checkedAt"] = timestamp
        if not path.exists():
            _write_json(path, payload)


def _refresh_runtime_data() -> list[str]:
    steps: list[tuple[str, str]] = [
        ("sync_agent_config", "Agent 配置已同步"),
        ("sync_officials_stats", "团队角色统计已同步"),
        ("refresh_live_data", "状态数据已刷新"),
    ]
    messages: list[str] = []
    for module_name, success_message in steps:
        try:
            _run_embedded_script(module_name)
            messages.append(success_message)
        except Exception as exc:
            messages.append(f"{module_name} 失败: {exc}")
    return messages


def provision_openclaw_runtime() -> dict:
    cli_bin = _resolve_openclaw_bin()
    if not cli_bin:
        return {
            "ok": False,
            "summary": "未检测到 OpenClaw CLI",
            "detail": "请先安装 OpenClaw CLI，再导入 RaccoonClaw-OSS 组织配置。",
            "output": "",
        }

    initialized, init_output = _ensure_openclaw_initialized()
    if not initialized:
        return {
            "ok": False,
            "summary": "OpenClaw 初始化失败",
            "detail": "OpenClaw 初始化向导没有成功完成，无法继续导入组织配置。",
            "output": init_output,
        }

    backup_dir = _backup_existing()
    cleanup = _cleanup_legacy_runtime_layout()
    cfg = _merge_agents_config()
    _write_json(OPENCLAW_CFG, cfg)
    _provision_workspaces()
    soul_count = _deploy_soul_files()
    synced = _sync_runtime_assets()
    auth_sync = _seed_auth_profiles()
    _initialize_data(cfg)

    gateway_ok, gateway_output = _run_openclaw(["gateway", "restart"], timeout=90)
    cfg_after_restart = _read_json(OPENCLAW_CFG, cfg)
    cfg_after_restart, token_synced = _sync_gateway_remote_token(cfg_after_restart)
    second_restart_ok = True
    second_restart_output = ""
    if token_synced:
        _write_json(OPENCLAW_CFG, cfg_after_restart)
        second_restart_ok, second_restart_output = _run_openclaw(["gateway", "restart"], timeout=90)
    sync_messages = _refresh_runtime_data()
    status = get_bootstrap_status()

    return {
        "ok": status["ready"],
        "summary": "RaccoonClaw-OSS 组织配置已导入" if status["ready"] else "RaccoonClaw-OSS 组织配置已写入，但 gateway 尚未就绪",
        "detail": "已创建当前 OpenClaw 配置备份。",
        "output": "\n".join(
            part for part in [
                f"SOUL 已部署: {soul_count}",
                f"脚本已同步: {synced['scripts']}",
                f"共享配置已同步: {synced['shared']}",
                f"共享技能已同步: {synced['skills']}",
                f"旧 workspace 已清理: {cleanup['workspaces']}",
                f"旧 agent 目录已清理: {cleanup['agents']}",
                f"组织认证已同步: {auth_sync['copied']}",
                "已复用现有 OpenClaw 认证文件" if auth_sync["source"] else "",
                f"Gateway token 已校准: {'已更新' if token_synced else '无需变更'}",
                f"Gateway 重启: {'成功' if gateway_ok else '失败'}",
                _sanitize_user_facing_text(gateway_output),
                f"Gateway 二次重启: {'成功' if second_restart_ok else '失败'}" if token_synced else "",
                _sanitize_user_facing_text(second_restart_output) if token_synced else "",
                *sync_messages,
            ]
            if part
        ),
        "backupDir": str(backup_dir),
        "gatewayRestarted": gateway_ok,
        "status": status,
    }

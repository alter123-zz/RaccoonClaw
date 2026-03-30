"""File-backed dashboard compatibility helpers for the FastAPI backend."""

from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import sys
import threading
from functools import lru_cache

from ..config import get_settings


log = logging.getLogger("edict.legacy_dashboard")
SETTINGS = get_settings()
if os.environ.get("OPENCLAW_PROJECT_ROOT", "").strip():
    ROOT = pathlib.Path(os.environ["OPENCLAW_PROJECT_ROOT"]).expanduser()
elif getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    ROOT = pathlib.Path(sys._MEIPASS)
else:
    ROOT = pathlib.Path(__file__).parents[4]
OCLAW_HOME = pathlib.Path(os.environ.get("OPENCLAW_HOME", str(pathlib.Path.home() / ".openclaw"))).expanduser()
REGISTRY_PATH = ROOT / "shared" / "agent-registry.json"
WORKFLOW_PATH = ROOT / "shared" / "workflow-config.json"
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from runtime_paths import canonical_data_dir, repo_data_dir
from automation_health import build_automation_snapshot
from utils import format_beijing
from workbench_modes import inject_mode_id


_LIVE_STATUS_REFRESH_LOCK = threading.Lock()
_RUNTIME_SYNC_MAX_AGE_SECONDS = 45


def _resolve_path(raw: str) -> pathlib.Path:
    path = pathlib.Path(raw).expanduser()
    if path.is_absolute():
        return path

    candidates = [(ROOT / path).resolve()]
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("../"):
        normalized = normalized[3:]
    if normalized and normalized != str(path):
        candidates.append((ROOT / normalized).resolve())

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def data_dir() -> pathlib.Path:
    configured = _resolve_path(SETTINGS.legacy_data_dir)
    runtime_dir = canonical_data_dir()
    return runtime_dir if runtime_dir.exists() else configured


def read_json_file(name: str, default):
    for base in (data_dir(), repo_data_dir()):
        path = base / name
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return default


def _path_mtime(path: pathlib.Path) -> float:
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def _parse_generated_at(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def _live_status_needs_refresh(base: pathlib.Path, live_path: pathlib.Path) -> bool:
    if not live_path.exists():
        return True

    live_mtime = _path_mtime(live_path)
    dependency_names = (
        "tasks_source.json",
        "tasks.json",
        "officials_stats.json",
        "sync_status.json",
    )
    latest_input_mtime = max(_path_mtime(base / name) for name in dependency_names)
    return latest_input_mtime > live_mtime


def _runtime_sync_needs_refresh(base: pathlib.Path) -> bool:
    sync_path = base / "sync_status.json"
    tasks_path = base / "tasks_source.json"
    if not sync_path.exists():
        return True

    sync_mtime = _path_mtime(sync_path)
    if not sync_mtime:
        return True

    age_seconds = datetime.datetime.now().timestamp() - sync_mtime
    if age_seconds > _RUNTIME_SYNC_MAX_AGE_SECONDS:
        return True

    return _path_mtime(tasks_path) > sync_mtime


def ensure_live_status_fresh() -> dict:
    base = data_dir()
    live_path = base / "live_status.json"
    with _LIVE_STATUS_REFRESH_LOCK:
        if _runtime_sync_needs_refresh(base):
            try:
                from sync_from_openclaw_runtime import main as sync_runtime_main

                sync_runtime_main()
            except Exception:
                log.exception("failed to sync openclaw runtime before serving dashboard data")
        if _live_status_needs_refresh(base, live_path):
            try:
                from refresh_live_data import main as refresh_live_data_main

                refresh_live_data_main()
            except Exception:
                log.exception("failed to refresh live_status.json before serving dashboard data")

    return normalize_live_status(read_json_file("live_status.json", {"tasks": []}))


def normalize_live_status(payload: dict | None) -> dict:
    data = payload if isinstance(payload, dict) else {}

    tasks = data.get("tasks")
    if isinstance(tasks, dict):
        data["tasks"] = list(tasks.values())
    elif not isinstance(tasks, list):
        data["tasks"] = []
    normalized_tasks = []
    for task in data["tasks"]:
        if not isinstance(task, dict):
            normalized_tasks.append(task)
            continue
        normalized_tasks.append(inject_mode_id(task))
    data["tasks"] = normalized_tasks

    sync_status = data.get("syncStatus")
    if not isinstance(sync_status, dict):
        sync_status = {}
    if "ok" not in sync_status:
        sync_status["ok"] = None
    data["syncStatus"] = sync_status

    health = data.get("health")
    if not isinstance(health, dict):
        health = {}
    if "syncOk" not in health:
        health["syncOk"] = sync_status.get("ok")
    data["health"] = health
    data["automation"] = build_automation_snapshot()

    return data


@lru_cache(maxsize=1)
def load_agent_registry() -> list[dict[str, str]]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_workflow_config() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def org_agent_map() -> dict[str, str]:
    return {agent["label"]: agent["id"] for agent in load_agent_registry()}


def _queue_snapshot() -> dict[str, int]:
    cfg = load_workflow_config()
    state_agent_map = cfg.get("stateAgentMap", {})
    org_resolved_states = set(cfg.get("orgResolvedStates", []))
    terminal_states = set(cfg.get("terminalStates", []))
    org_map = org_agent_map()

    counts: dict[str, int] = {}
    for task in read_json_file("tasks_source.json", []):
        if task.get("archived"):
            continue
        state = str(task.get("state") or "").strip()
        if not state or state in terminal_states:
            continue
        agent_id = state_agent_map.get(state)
        if not agent_id and state in org_resolved_states:
            agent_id = org_map.get(str(task.get("org") or "").strip())
        if not agent_id:
            continue
        counts[agent_id] = counts.get(agent_id, 0) + 1
    return counts


def _check_gateway_alive() -> bool:
    """使用官方命令精准检测网关存活性。"""
    try:
        # 直接运行官方状态检查，这是最权威的
        result = subprocess.run(
            ["openclaw", "gateway", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "Runtime: running" in result.stdout
    except Exception:
        # Fallback to pgrep
        try:
            res = subprocess.run(["pgrep", "-f", "openclaw.*gateway"], capture_output=True)
            return res.returncode == 0
        except:
            return False


def _check_gateway_probe() -> bool:
    """探测网关响应能力。"""
    try:
        # 如果 status 命令显示 RPC probe: ok，则认为探测成功
        result = subprocess.run(
            ["openclaw", "gateway", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "RPC probe: ok" in result.stdout:
            return True
        
        # 兜底网络请求
        resp = urlopen(SETTINGS.openclaw_gateway_url, timeout=2)
        return resp.status in (200, 401) # 401 也说明网关是开着的，只是需要 Token
    except Exception:
        return False


def _get_agent_session_status(agent_id: str) -> tuple[int, int, bool]:
    sessions_file = OCLAW_HOME / "agents" / agent_id / "sessions" / "sessions.json"
    if not sessions_file.exists():
        return 0, 0, False
    try:
        data = json.loads(sessions_file.read_text(encoding="utf-8"))
    except Exception:
        return 0, 0, False
    if not isinstance(data, dict):
        return 0, 0, False
    session_count = len(data)
    last_ts = 0
    for row in data.values():
        ts = row.get("updatedAt", 0)
        if isinstance(ts, (int, float)) and ts > last_ts:
            last_ts = int(ts)
    now_ms = int(datetime.datetime.now().timestamp() * 1000)
    age_ms = now_ms - last_ts if last_ts else 9999999999
    is_busy = age_ms <= 2 * 60 * 1000
    return last_ts, session_count, is_busy


def _check_agent_process(agent_id: str) -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", f"openclaw.*--agent.*{agent_id}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_agent_workspace(agent_id: str) -> bool:
    return (OCLAW_HOME / f"workspace-{agent_id}").is_dir()


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def get_agents_status() -> dict:
    gateway_alive = _check_gateway_alive()
    gateway_probe = _check_gateway_probe() if gateway_alive else False
    try:
        queue_counts = _queue_snapshot()
        agents = []
        for agent in load_agent_registry():
            agent_id = agent["id"]
            has_workspace = _check_agent_workspace(agent_id)
            last_ts, sessions, is_busy = _get_agent_session_status(agent_id)
            process_alive = _check_agent_process(agent_id)
            queued_tasks = queue_counts.get(agent_id, 0)

            if not has_workspace:
                status = "unconfigured"
                status_label = "❌ 未配置"
            elif not gateway_alive:
                status = "offline"
                status_label = "🔴 Gateway 离线"
            elif process_alive or is_busy:
                status = "running"
                status_label = "🟢 运行中"
            elif queued_tasks > 0:
                status = "queued"
                status_label = f"🟠 待处理 · {queued_tasks}项"
            else:
                status = "idle"
                if last_ts > 0:
                    now_ms = int(datetime.datetime.now().timestamp() * 1000)
                    age_ms = now_ms - last_ts
                    if age_ms <= 10 * 60 * 1000:
                        status_label = "🟡 待命"
                    elif age_ms <= 3600 * 1000:
                        status_label = "⚪ 空闲"
                    else:
                        status_label = "⚪ 休眠"
                else:
                    status_label = "⚪ 无记录"

            last_active = None
            if last_ts > 0:
                try:
                    last_active = format_beijing(last_ts, "%m-%d %H:%M")
                except Exception:
                    last_active = None

            agents.append(
                {
                    "id": agent_id,
                    "label": agent["label"],
                    "emoji": agent["emoji"],
                    "role": agent["displayRole"],
                    "status": status,
                    "statusLabel": status_label,
                    "lastActive": last_active,
                    "lastActiveTs": last_ts,
                    "sessions": sessions,
                    "hasWorkspace": has_workspace,
                    "processAlive": process_alive,
                    "queuedTasks": queued_tasks,
                }
            )
        ok = True
        error = ""
    except Exception as exc:
        log.exception("failed to build agents status")
        agents = []
        for agent in load_agent_registry():
            agent_id = agent["id"]
            agents.append(
                {
                    "id": agent_id,
                    "label": agent["label"],
                    "emoji": agent["emoji"],
                    "role": agent["displayRole"],
                    "status": "offline",
                    "statusLabel": "🔴 状态读取失败",
                    "lastActive": None,
                    "lastActiveTs": 0,
                    "sessions": 0,
                    "hasWorkspace": _check_agent_workspace(agent_id),
                    "processAlive": False,
                    "queuedTasks": 0,
                }
            )
        ok = False
        error = str(exc)

    return {
        "ok": ok,
        "error": error,
        "gateway": {
            "alive": gateway_alive,
            "probe": gateway_probe,
            "status": "🟢 运行中" if gateway_probe else ("🟡 进程在但无响应" if gateway_alive else "🔴 未启动"),
        },
        "agents": agents,
        "checkedAt": now_iso(),
    }

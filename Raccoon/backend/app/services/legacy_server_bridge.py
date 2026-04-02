"""Bridge selected dashboard server behaviors into the FastAPI backend."""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import mimetypes
import os
import plistlib
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from .legacy_dashboard import data_dir
from .runtime_bootstrap import get_desktop_startup_status
from ..config import get_settings


SETTINGS = get_settings()
if os.environ.get("OPENCLAW_PROJECT_ROOT", "").strip():
    ROOT = Path(os.environ["OPENCLAW_PROJECT_ROOT"]).expanduser()
elif getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).parents[4]
SERVER_PATH = ROOT / "dashboard" / "server.py"
OPENCLAW_CFG = Path(os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw"))).expanduser() / "openclaw.json"
AGENT_REGISTRY_PATH = ROOT / "shared" / "agent-registry.json"
WECHAT_INSTALL_COMMAND = [
    "npx",
    "-y",
    "@tencent-weixin/openclaw-weixin-cli@latest",
    "install",
]
_CHAT_LOCK = threading.Lock()

TEXT_ATTACHMENT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".json", ".csv", ".tsv", ".log", ".py", ".js", ".ts", ".tsx",
    ".jsx", ".css", ".html", ".htm", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".sh",
    ".zsh", ".bash", ".sql",
}
_TEXTUTIL_EXTENSIONS = {".doc", ".docx", ".rtf", ".rtfd", ".odt", ".html", ".htm", ".webarchive"}

AGENT_ID_DISPLAY_ALIASES = {
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

IM_CHANNEL_SPECS = {
    "feishu": {
        "label": "飞书",
        "icon": "🪽",
        "description": "飞书机器人与消息通道接入",
        "setupMode": "scan_or_manual",
        "capabilities": ["扫码接入", "App ID / Secret", "Gateway 重载"],
    },
    "wecom": {
        "label": "企业微信",
        "icon": "💼",
        "description": "企业微信 AI Bot 与会话接入",
        "setupMode": "scan_or_manual",
        "capabilities": ["扫码创建机器人", "Bot ID / Secret", "WebSocket"],
    },
    "dingtalk": {
        "label": "钉钉",
        "icon": "🪽",
        "description": "钉钉插件安装与应用凭据配置",
        "setupMode": "plugin_then_manual",
        "capabilities": ["插件安装", "Client ID / Secret", "状态刷新"],
    },
    "qqbot": {
        "label": "QQ Bot",
        "icon": "🐧",
        "description": "QQ Bot App 凭据和私聊策略配置",
        "setupMode": "manual",
        "capabilities": ["App ID / Secret", "私聊策略", "高级选项"],
    },
    "weixin": {
        "label": "微信",
        "icon": "💬",
        "description": "微信 ClawBot 环境检查与命令引导",
        "setupMode": "guided",
        "capabilities": ["环境检查", "复制命令", "状态检测"],
    },
}

_RUNTIME_DIAGNOSTIC_PREFIXES = (
    "Gateway 通道调用失败",
    "Gateway 连接失败",
    "Gateway target:",
    "Source:",
    "Config:",
    "Bind:",
    "[tools]",
    "[diagnostic]",
    "[model-fallback/decision]",
    "FailoverError:",
)


def _load_agent_registry() -> list[dict]:
    try:
        return json.loads(AGENT_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _extract_runtime_payload_text(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    match = re.search(r'"text"\s*:\s*"((?:\\.|[^"\\])*)"', text, flags=re.S)
    if match:
        try:
            candidate = json.loads(f'"{match.group(1)}"')
        except Exception:
            candidate = match.group(1).replace('\\"', '"').replace("\\n", "\n")
        candidate = str(candidate).strip()
        if candidate:
            return candidate
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            parsed, end = decoder.raw_decode(text[match.start():])
        except Exception:
            continue
        if str(text[match.start() + end:]).strip():
            continue
        result = parsed.get("result") if isinstance(parsed, dict) else None
        payloads = result.get("payloads") if isinstance(result, dict) else None
        if not isinstance(payloads, list):
            continue
        chunks = [
            str(item.get("text") or "").strip()
            for item in payloads
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
        if chunks:
            return "\n\n".join(chunks).strip()
    return ""


def _strip_runtime_diagnostics(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    payload_text = _extract_runtime_payload_text(text)
    if payload_text:
        return payload_text
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if kept and kept[-1]:
                kept.append("")
            continue
        if any(stripped.startswith(prefix) for prefix in _RUNTIME_DIAGNOSTIC_PREFIXES):
            continue
        if stripped.startswith("{") or stripped.startswith('"payloads"') or stripped.startswith('"meta"'):
            continue
        if stripped.startswith("}") or stripped.startswith('"systemPromptReport"') or stripped.startswith('"tools"'):
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def _official_for_org(org: str) -> str:
    for item in _load_agent_registry():
        if str(item.get("label") or "").strip() == str(org or "").strip():
            return str(item.get("displayRole") or "").strip() or "负责人"
    fallback_map = {
        "总裁办": "Chief of Staff",
        "产品规划部": "产品规划负责人",
        "评审质控部": "评审质控负责人",
        "交付运营部": "交付运营负责人",
        "品牌内容部": "品牌内容负责人",
        "经营分析部": "经营分析负责人",
        "安全运维部": "安全运维负责人",
        "合规测试部": "合规测试负责人",
        "工程研发部": "工程研发负责人",
        "人力组织部": "人力组织负责人",
    }
    return fallback_map.get(str(org or "").strip(), "负责人")


def _chat_sessions_path() -> Path:
    return data_dir() / "chat_sessions.json"


def _chat_uploads_dir() -> Path:
    return data_dir() / "chat_uploads"


def _im_channels_path() -> Path:
    return data_dir() / "im_channels.json"


def _desktop_path_env() -> str:
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


def _resolve_openclaw_bin() -> str:
    explicit = os.environ.get("OPENCLAW_BIN", "").strip()
    if explicit and Path(explicit).is_file():
        return explicit
    detected = shutil.which(SETTINGS.openclaw_bin) or shutil.which("openclaw")
    return detected or SETTINGS.openclaw_bin


def _toolbox_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = _desktop_path_env()
    env["OPENCLAW_BIN"] = _resolve_openclaw_bin()
    env.pop("OPENCLAW_HOME", None)
    env.pop("OPENCLAW_WORKSPACE", None)
    return env


def _desktop_mode_enabled() -> bool:
    return os.environ.get("OPENCLAW_APP_MODE", "").strip().lower() == "desktop"


def _normalize_toolbox_cmd(cmd: list[str]) -> list[str]:
    if not cmd:
        return cmd
    head = cmd[0]
    if head in {SETTINGS.openclaw_bin, "openclaw"}:
        resolved = _resolve_openclaw_bin()
        return [resolved, *cmd[1:]]
    return cmd


def _run_embedded_script(module_name: str) -> dict:
    scripts_root = ROOT / "scripts"
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))
    spec = importlib.util.spec_from_file_location(
        f"edictclaw_{module_name}",
        scripts_root / f"{module_name}.py",
    )
    if spec is None or spec.loader is None:
        return {
            "ok": False,
            "action": module_name,
            "message": f"无法加载脚本: {module_name}",
            "stdout": "",
            "stderr": "",
            "code": None,
            "executedAt": datetime.now().isoformat(timespec="seconds"),
        }

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        module = importlib.util.module_from_spec(spec)
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            spec.loader.exec_module(module)
            entry = getattr(module, "main", None)
            if not callable(entry):
                raise RuntimeError(f"{module_name}.py 缺少 main()")
            entry()
        return {
            "ok": True,
            "action": module_name,
            "message": "执行成功",
            "stdout": stdout_buffer.getvalue().strip(),
            "stderr": stderr_buffer.getvalue().strip(),
            "code": 0,
            "executedAt": datetime.now().isoformat(timespec="seconds"),
        }
    except Exception as exc:
        stderr = stderr_buffer.getvalue().strip()
        stderr = f"{stderr}\n{exc}".strip() if stderr else str(exc)
        return {
            "ok": False,
            "action": module_name,
            "message": "执行失败",
            "stdout": stdout_buffer.getvalue().strip(),
            "stderr": stderr,
            "code": 1,
            "executedAt": datetime.now().isoformat(timespec="seconds"),
        }


@lru_cache(maxsize=1)
def load_legacy_server_module():
    if not SERVER_PATH.exists():
        raise RuntimeError(f"Dashboard server module not found: {SERVER_PATH}")
    spec = importlib.util.spec_from_file_location("openclaw_workbench_dashboard_server", SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load dashboard server module from {SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_task_activity(task_id: str) -> dict:
    return load_legacy_server_module().get_task_activity(task_id)


def get_scheduler_state(task_id: str) -> dict:
    return load_legacy_server_module().get_scheduler_state(task_id)


def read_skill_content(agent_id: str, skill_name: str) -> dict:
    return load_legacy_server_module().read_skill_content(agent_id, skill_name)


def get_remote_skills_list() -> dict:
    return load_legacy_server_module().get_remote_skills_list()


def get_available_skills_catalog() -> dict:
    return load_legacy_server_module().get_available_skills_catalog()


def create_task(
    title: str,
    org: str,
    official: str,
    priority: str,
    template_id: str,
    params: dict,
    target_dept: str,
    mode_id: str = "",
    flow_mode: str = "full",
) -> dict:
    return load_legacy_server_module().handle_create_task(
        title,
        org,
        official,
        priority,
        template_id,
        params,
        target_dept,
        mode_id,
        flow_mode,
    )


def task_action(task_id: str, action: str, reason: str) -> dict:
    return load_legacy_server_module().handle_task_action(task_id, action, reason)


def review_action(task_id: str, action: str, comment: str) -> dict:
    return load_legacy_server_module().handle_review_action(task_id, action, comment)


def advance_state(task_id: str, comment: str) -> dict:
    return load_legacy_server_module().handle_advance_state(task_id, comment)


def archive_task(task_id: str, archived: bool, archive_all_done: bool = False) -> dict:
    return load_legacy_server_module().handle_archive_task(task_id, archived, archive_all_done)


def update_task_todos(task_id: str, todos: list[dict]) -> dict:
    return load_legacy_server_module().update_task_todos(task_id, todos)


def wake_agent(agent_id: str, message: str = "") -> dict:
    return load_legacy_server_module().wake_agent(agent_id, message)


def scheduler_scan(threshold_sec: int = 180) -> dict:
    if _desktop_mode_enabled():
        startup = get_desktop_startup_status()
        if not startup.get("ready"):
            summary = str(startup.get("summary") or "桌面端尚未完成启动")
            detail = str(startup.get("detail") or "请先完成 OpenClaw、Gateway 和组织配置检查。")
            return {
                "ok": False,
                "blocked": True,
                "count": 0,
                "actions": [],
                "checkedAt": "",
                "summary": summary,
                "detail": detail,
                "message": f"{summary}：{detail}",
            }
    return load_legacy_server_module().handle_scheduler_scan(threshold_sec)


def run_due_scheduled_jobs() -> dict:
    if _desktop_mode_enabled():
        startup = get_desktop_startup_status()
        if not startup.get("ready"):
            summary = str(startup.get("summary") or "桌面端尚未完成启动")
            detail = str(startup.get("detail") or "请先完成 OpenClaw、Gateway 和组织配置检查。")
            return {
                "ok": False,
                "blocked": True,
                "count": 0,
                "actions": [],
                "checkedAt": "",
                "summary": summary,
                "detail": detail,
                "message": f"{summary}：{detail}",
            }
    return load_legacy_server_module().handle_run_due_scheduled_jobs()


def scheduler_retry(task_id: str, reason: str = "") -> dict:
    return load_legacy_server_module().handle_scheduler_retry(task_id, reason)


def scheduler_escalate(task_id: str, reason: str = "") -> dict:
    return load_legacy_server_module().handle_scheduler_escalate(task_id, reason)


def scheduler_rollback(task_id: str, reason: str = "") -> dict:
    return load_legacy_server_module().handle_scheduler_rollback(task_id, reason)


def add_skill(agent_id: str, skill_name: str, description: str, trigger: str = "") -> dict:
    return load_legacy_server_module().add_skill_to_agent(agent_id, skill_name, description, trigger)


def add_remote_skill(agent_id: str, skill_name: str, source_url: str, description: str = "") -> dict:
    return load_legacy_server_module().add_remote_skill(agent_id, skill_name, source_url, description)


def repair_flow_order() -> dict:
    return load_legacy_server_module().handle_repair_flow_order()


def update_remote_skill(agent_id: str, skill_name: str) -> dict:
    return load_legacy_server_module().update_remote_skill(agent_id, skill_name)


def remove_remote_skill(agent_id: str, skill_name: str) -> dict:
    return load_legacy_server_module().remove_remote_skill(agent_id, skill_name)


def open_local_path(path: str) -> dict:
    target = Path(str(path or "")).expanduser()
    if not str(target).strip():
        return {"ok": False, "error": "path 不能为空"}
    if not target.exists():
        return {"ok": False, "error": f"路径不存在: {target}"}
    return _run_toolbox_command(["open", str(target)], timeout=20, output_limit=2000)


def queue_model_change(agent_id: str, model: str) -> dict:
    server = load_legacy_server_module()
    pending_path = data_dir() / "pending_model_changes.json"

    def update_pending(current):
        current = [x for x in current if x.get("agentId") != agent_id]
        current.append({"agentId": agent_id, "model": model})
        return current

    server.atomic_json_update(pending_path, update_pending, [])

    def apply_async():
        try:
            if _desktop_mode_enabled():
                _run_embedded_script("apply_model_changes")
                _run_embedded_script("sync_agent_config")
            else:
                subprocess.run(["python3", str(server.SCRIPTS / "apply_model_changes.py")], timeout=30)
                subprocess.run(["python3", str(server.SCRIPTS / "sync_agent_config.py")], timeout=10)
        except Exception:
            pass

    threading.Thread(target=apply_async, daemon=True).start()
    return {"ok": True, "message": f"Queued: {agent_id} → {model}"}


def _slugify_provider_key(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return text or "custom"


def _normalize_base_url(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def _map_api_protocol(protocol: str) -> str:
    normalized = str(protocol or "").strip().lower()
    if normalized == "anthropic":
        return "anthropic-messages"
    return "openai-completions"


def _resolve_provider_id(
    providers: dict,
    vendor_key: str,
    base_url: str,
    api_name: str,
    api_key: str,
) -> str:
    base_id = _slugify_provider_key(vendor_key)
    target_base = _normalize_base_url(base_url)
    target_api = str(api_name or "").strip()
    target_key = str(api_key or "").strip()
    for provider_id, provider_cfg in providers.items():
        current_base = _normalize_base_url(provider_cfg.get("baseUrl", ""))
        current_api = str(provider_cfg.get("api", "")).strip()
        current_key = str(provider_cfg.get("apiKey", "")).strip()
        if _slugify_provider_key(provider_id) != base_id and not str(provider_id).startswith(f"{base_id}-"):
            continue
        if current_base == target_base and current_api == target_api and current_key == target_key:
            return str(provider_id)
    if base_id not in providers:
        return base_id
    suffix = 2
    while f"{base_id}-{suffix}" in providers:
        suffix += 1
    return f"{base_id}-{suffix}"


def add_model_catalog_entry(
    vendor_key: str,
    model_id: str,
    model_name: str,
    provider_label: str = "",
    base_url: str = "",
    api_protocol: str = "openai",
    api_key: str = "",
    auth_header: bool = True,
    reasoning: bool = False,
    context_window: int | None = None,
    max_tokens: int | None = None,
) -> dict:
    vendor_key = str(vendor_key or "").strip()
    model_id = str(model_id or "").strip()
    model_name = str(model_name or "").strip()
    provider_label = str(provider_label or "").strip()
    base_url = _normalize_base_url(base_url)
    api_key = str(api_key or "").strip()
    api = _map_api_protocol(api_protocol)

    if not vendor_key:
        return {"ok": False, "error": "服务商不能为空"}
    if not model_id:
        return {"ok": False, "error": "modelId 不能为空"}
    if not model_name:
        return {"ok": False, "error": "模型名称不能为空"}
    if not base_url:
        return {"ok": False, "error": "Base URL 不能为空"}

    cfg = _read_openclaw_config()
    models_cfg = cfg.setdefault("models", {})
    models_cfg.setdefault("mode", "merge")
    providers = models_cfg.setdefault("providers", {})

    provider_id = _resolve_provider_id(providers, vendor_key, base_url, api, api_key)
    is_new_provider = provider_id not in providers

    provider_cfg = providers.setdefault(provider_id, {})
    provider_cfg["baseUrl"] = base_url
    provider_cfg["api"] = api
    provider_cfg["authHeader"] = bool(auth_header)
    if api_key:
        provider_cfg["apiKey"] = api_key
    provider_models = provider_cfg.setdefault("models", [])

    normalized_model_id = model_id.split("/", 1)[1] if "/" in model_id else model_id
    full_model_id = f"{provider_id}/{normalized_model_id}"

    for item in provider_models:
        item_id = str(item.get("id") or "").strip()
        if item_id == normalized_model_id:
            return {"ok": False, "error": f"模型已存在：{full_model_id}"}

    model_payload = {
        "id": normalized_model_id,
        "name": model_name,
        "reasoning": bool(reasoning),
    }
    if isinstance(context_window, int) and context_window > 0:
        model_payload["contextWindow"] = context_window
    if isinstance(max_tokens, int) and max_tokens > 0:
        model_payload["maxTokens"] = max_tokens
    provider_models.append(model_payload)

    defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})
    defaults_models = defaults.setdefault("models", {})
    defaults_models.setdefault(full_model_id, {"alias": model_name})

    backup = _write_openclaw_config(cfg)

    def apply_async():
        try:
            if _desktop_mode_enabled():
                _run_embedded_script("sync_agent_config")
            else:
                subprocess.run(["python3", str(load_legacy_server_module().SCRIPTS / "sync_agent_config.py")], timeout=10)
        except Exception:
            pass

    threading.Thread(target=apply_async, daemon=True).start()
    return {
        "ok": True,
        "message": f"已添加模型：{full_model_id}",
        "modelId": full_model_id,
        "providerId": provider_id,
        "backup": str(backup),
    }


def test_model_connection(
    base_url: str,
    api_protocol: str,
    model_id: str,
    api_key: str = "",
) -> dict:
    base_url = _normalize_base_url(base_url)
    protocol = str(api_protocol or "").strip().lower()
    model_id = str(model_id or "").strip()
    api_key = str(api_key or "").strip()
    if not base_url:
        return {"ok": False, "error": "Base URL 不能为空"}
    if not model_id:
        return {"ok": False, "error": "模型 ID 不能为空"}

    if protocol == "anthropic":
        endpoint = base_url if base_url.endswith("/messages") else f"{base_url}/messages"
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if api_key:
            headers["x-api-key"] = api_key
        payload = {
            "model": model_id,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
    else:
        endpoint = base_url
        if not endpoint.endswith("/chat/completions"):
            if endpoint.endswith("/v1") or endpoint.endswith("/v4"):
                endpoint = f"{endpoint}/chat/completions"
            else:
                endpoint = f"{endpoint}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }

    req = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.time()
    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read(800).decode("utf-8", errors="ignore")
            duration_ms = int((time.time() - started) * 1000)
            return {
                "ok": True,
                "message": "连通测试通过",
                "status": getattr(resp, "status", 200),
                "durationMs": duration_ms,
                "preview": body[:300],
            }
    except HTTPError as exc:
        try:
            detail = exc.read(800).decode("utf-8", errors="ignore")
        except Exception:
            detail = str(exc)
        return {
            "ok": False,
            "error": f"HTTP {exc.code}: {detail[:300] or exc.reason}",
        }
    except URLError as exc:
        return {"ok": False, "error": f"连接失败: {exc.reason}"}
    except Exception as exc:
        return {"ok": False, "error": f"测试失败: {exc}"}


def _read_openclaw_config() -> dict:
    if not OPENCLAW_CFG.exists():
        return {}
    try:
        return json.loads(OPENCLAW_CFG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_openclaw_config(payload: dict) -> Path:
    OPENCLAW_CFG.parent.mkdir(parents=True, exist_ok=True)
    backup = OPENCLAW_CFG.parent / f"openclaw.json.bak.toolbox-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if OPENCLAW_CFG.exists():
        shutil.copy2(OPENCLAW_CFG, backup)
    OPENCLAW_CFG.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup


def _read_im_channels_store() -> dict:
    path = _im_channels_path()
    if not path.exists():
        return {"channels": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("channels"), dict):
            return payload
    except Exception:
        pass
    return {"channels": {}}


def _write_im_channels_store(payload: dict) -> None:
    path = _im_channels_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _mask_secret(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return value[:3] + "…" + value[-2:]


def _normalize_im_channel_key(channel_key: str) -> str:
    key = str(channel_key or "").strip().lower()
    if key not in IM_CHANNEL_SPECS:
        raise ValueError(f"不支持的频道类型: {channel_key}")
    return key


def _im_channel_enabled(channel_cfg: dict) -> bool:
    if not isinstance(channel_cfg, dict):
        return False
    return bool(channel_cfg.get("enabled", True))


def _get_channel_section(config: dict, channel_key: str) -> dict:
    channels = config.get("channels")
    if not isinstance(channels, dict):
        return {}
    channel_cfg = channels.get(channel_key)
    return channel_cfg if isinstance(channel_cfg, dict) else {}


def _get_im_channel_ui_entry(store: dict, channel_key: str) -> dict:
    channels = store.get("channels")
    if not isinstance(channels, dict):
        return {}
    item = channels.get(channel_key)
    return item if isinstance(item, dict) else {}


def _channel_config_summary(channel_key: str, channel_cfg: dict) -> dict:
    channel_cfg = channel_cfg if isinstance(channel_cfg, dict) else {}
    if channel_key == "feishu":
        accounts = channel_cfg.get("accounts") if isinstance(channel_cfg.get("accounts"), dict) else {}
        account = accounts.get(str(channel_cfg.get("defaultAccount") or "main")) if isinstance(accounts.get(str(channel_cfg.get("defaultAccount") or "main")), dict) else {}
        return {
            "接入方式": "手动凭据",
            "App ID": str(account.get("appId") or ""),
            "域名": str(account.get("domain") or channel_cfg.get("domain") or "feishu"),
            "Bot 名称": str(account.get("botName") or ""),
        }
    if channel_key == "wecom":
        return {
            "接入方式": str(channel_cfg.get("setupMode") or "扫码或手动"),
            "Bot ID": str(channel_cfg.get("botId") or ""),
            "Secret": _mask_secret(str(channel_cfg.get("botSecret") or "")),
        }
    if channel_key == "dingtalk":
        return {
            "接入方式": str(channel_cfg.get("setupMode") or "插件 + 凭据"),
            "Client ID": str(channel_cfg.get("clientId") or ""),
            "插件状态": "已安装" if channel_cfg.get("pluginInstalled") else "未安装",
        }
    if channel_key == "qqbot":
        accounts = channel_cfg.get("accounts") if isinstance(channel_cfg.get("accounts"), dict) else {}
        account = accounts.get("main") if isinstance(accounts.get("main"), dict) else {}
        return {
            "App ID": str(account.get("appId") or ""),
            "Secret": _mask_secret(str(account.get("appSecret") or "")),
            "私聊策略": str(channel_cfg.get("privateChatPolicy") or "open"),
        }
    if channel_key == "weixin":
        return {
            "接入方式": str(channel_cfg.get("setupMode") or "向导引导"),
            "插件状态": "已安装" if channel_cfg.get("pluginInstalled") else "未安装",
            "环境状态": str(channel_cfg.get("environmentStatus") or "未检查"),
        }
    return {}


def _channel_checks(channel_key: str, channel_cfg: dict) -> list[dict]:
    checks: list[dict] = []
    if channel_key == "feishu":
        accounts = channel_cfg.get("accounts") if isinstance(channel_cfg.get("accounts"), dict) else {}
        account = accounts.get(str(channel_cfg.get("defaultAccount") or "main")) if isinstance(accounts.get(str(channel_cfg.get("defaultAccount") or "main")), dict) else {}
        checks.append({
            "key": "app_id",
            "label": "App ID",
            "ok": bool(str(account.get("appId") or "").strip()),
            "detail": "已填写" if str(account.get("appId") or "").strip() else "未填写",
        })
        checks.append({
            "key": "app_secret",
            "label": "App Secret",
            "ok": bool(str(account.get("appSecret") or "").strip()),
            "detail": "已保存" if str(account.get("appSecret") or "").strip() else "未保存",
        })
    elif channel_key == "wecom":
        checks.append({
            "key": "bot_id",
            "label": "Bot ID",
            "ok": bool(str(channel_cfg.get("botId") or "").strip()),
            "detail": "已填写" if str(channel_cfg.get("botId") or "").strip() else "未填写",
        })
        checks.append({
            "key": "bot_secret",
            "label": "Bot Secret",
            "ok": bool(str(channel_cfg.get("botSecret") or "").strip()),
            "detail": "已保存" if str(channel_cfg.get("botSecret") or "").strip() else "未保存",
        })
    elif channel_key == "dingtalk":
        checks.append({
            "key": "plugin",
            "label": "插件安装",
            "ok": bool(channel_cfg.get("pluginInstalled")),
            "detail": "已安装" if channel_cfg.get("pluginInstalled") else "待安装",
        })
        checks.append({
            "key": "client_id",
            "label": "Client ID",
            "ok": bool(str(channel_cfg.get("clientId") or "").strip()),
            "detail": "已填写" if str(channel_cfg.get("clientId") or "").strip() else "未填写",
        })
    elif channel_key == "qqbot":
        accounts = channel_cfg.get("accounts") if isinstance(channel_cfg.get("accounts"), dict) else {}
        account = accounts.get("main") if isinstance(accounts.get("main"), dict) else {}
        checks.append({
            "key": "app_id",
            "label": "App ID",
            "ok": bool(str(account.get("appId") or "").strip()),
            "detail": "已填写" if str(account.get("appId") or "").strip() else "未填写",
        })
        checks.append({
            "key": "app_secret",
            "label": "App Secret",
            "ok": bool(str(account.get("appSecret") or "").strip()),
            "detail": "已保存" if str(account.get("appSecret") or "").strip() else "未保存",
        })
    elif channel_key == "weixin":
        env = _detect_wechat_environment()
        checks.append({
            "key": "wechat_app",
            "label": "WeChat.app",
            "ok": bool(env.get("appInstalled")),
            "detail": env.get("version") or "未安装",
        })
        checks.append({
            "key": "node_npx",
            "label": "Node / npx",
            "ok": bool(env.get("nodeAvailable")) and bool(env.get("npxAvailable")),
            "detail": "已检测到" if bool(env.get("nodeAvailable")) and bool(env.get("npxAvailable")) else "缺少环境",
        })
    return checks


def _channel_configured(channel_key: str, channel_cfg: dict) -> bool:
    checks = _channel_checks(channel_key, channel_cfg)
    if not checks:
        return False
    required_failures = [item for item in checks if item["key"] not in {"plugin"} and not item["ok"]]
    return not required_failures


def _build_im_channel_status(channel_key: str, config: dict, store: dict) -> dict:
    spec = IM_CHANNEL_SPECS[channel_key]
    channel_cfg = _get_channel_section(config, channel_key)
    ui_entry = _get_im_channel_ui_entry(store, channel_key)
    configured = _channel_configured(channel_key, channel_cfg)
    enabled = _im_channel_enabled(channel_cfg) or bool(ui_entry.get("enabled"))
    if configured and enabled:
        status = "configured"
        status_label = "已配置"
    elif configured and not enabled:
        status = "disabled"
        status_label = "已停用"
    elif channel_cfg or ui_entry:
        status = "draft"
        status_label = "未完成"
    else:
        status = "draft"
        status_label = "未配置"
    checks = _channel_checks(channel_key, channel_cfg)
    summary = {
        "configured": "配置已完成，可交给 Gateway 加载",
        "disabled": "已保存配置，当前处于停用状态",
        "draft": "已创建接入草稿，还需要补全配置",
        "error": "配置异常，需要重新检查",
    }.get(status, spec["description"])
    return {
        "key": channel_key,
        "label": spec["label"],
        "description": spec["description"],
        "icon": spec["icon"],
        "configured": configured,
        "enabled": enabled,
        "status": status,
        "statusLabel": status_label,
        "setupMode": str(ui_entry.get("setupMode") or channel_cfg.get("setupMode") or spec["setupMode"]),
        "summary": summary,
        "lastUpdated": str(ui_entry.get("updatedAt") or ui_entry.get("createdAt") or ""),
        "configSummary": _channel_config_summary(channel_key, channel_cfg),
        "checks": checks,
        "capabilities": list(spec.get("capabilities") or []),
    }


def get_im_channels_status() -> dict:
    config = _read_openclaw_config()
    store = _read_im_channels_store()
    channels = [_build_im_channel_status(channel_key, config, store) for channel_key in IM_CHANNEL_SPECS]
    return {
        "ok": True,
        "checkedAt": datetime.now().isoformat(timespec="seconds"),
        "channels": channels,
        "configuredCount": sum(1 for item in channels if item.get("configured")),
    }


def _ensure_channels_root(config: dict) -> dict:
    channels = config.get("channels")
    if not isinstance(channels, dict):
        channels = {}
        config["channels"] = channels
    return channels


def _write_im_channel_config(channel_key: str, enabled: bool, setup_mode: str, payload: dict) -> tuple[dict, dict]:
    config = _read_openclaw_config()
    store = _read_im_channels_store()
    channels = _ensure_channels_root(config)
    now = datetime.now().isoformat(timespec="seconds")
    current = channels.get(channel_key)
    if not isinstance(current, dict):
        current = {}
    payload = payload if isinstance(payload, dict) else {}

    if channel_key == "feishu":
        accounts = current.get("accounts") if isinstance(current.get("accounts"), dict) else {}
        account = accounts.get(str(current.get("defaultAccount") or "main")) if isinstance(accounts.get(str(current.get("defaultAccount") or "main")), dict) else {}
        app_secret = str(payload.get("appSecret") or "").strip() or str(account.get("appSecret") or "")
        account.update({
            "appId": str(payload.get("appId") or account.get("appId") or "").strip(),
            "appSecret": app_secret,
            "domain": str(payload.get("domain") or account.get("domain") or "feishu").strip() or "feishu",
            "botName": str(payload.get("botName") or account.get("botName") or "").strip(),
        })
        accounts["main"] = account
        current.update({
            "enabled": enabled,
            "defaultAccount": "main",
            "accounts": accounts,
            "domain": account.get("domain") or "feishu",
            "dmPolicy": str(payload.get("dmPolicy") or current.get("dmPolicy") or "pairing"),
            "groupPolicy": str(payload.get("groupPolicy") or current.get("groupPolicy") or "open"),
            "connectionMode": str(payload.get("connectionMode") or current.get("connectionMode") or "websocket"),
            "setupMode": setup_mode or "scan_or_manual",
        })
    elif channel_key == "wecom":
        bot_secret = str(payload.get("botSecret") or "").strip() or str(current.get("botSecret") or "")
        current.update({
            "enabled": enabled,
            "setupMode": setup_mode or "scan_or_manual",
            "botId": str(payload.get("botId") or current.get("botId") or "").strip(),
            "botSecret": bot_secret,
            "wsUrl": str(payload.get("wsUrl") or current.get("wsUrl") or "").strip(),
            "botName": str(payload.get("botName") or current.get("botName") or "").strip(),
        })
    elif channel_key == "dingtalk":
        client_secret = str(payload.get("clientSecret") or "").strip() or str(current.get("clientSecret") or "")
        current.update({
            "enabled": enabled,
            "setupMode": setup_mode or "plugin_then_manual",
            "pluginInstalled": bool(payload.get("pluginInstalled") if payload.get("pluginInstalled") is not None else current.get("pluginInstalled")),
            "clientId": str(payload.get("clientId") or current.get("clientId") or "").strip(),
            "clientSecret": client_secret,
        })
    elif channel_key == "qqbot":
        accounts = current.get("accounts") if isinstance(current.get("accounts"), dict) else {}
        account = accounts.get("main") if isinstance(accounts.get("main"), dict) else {}
        app_secret = str(payload.get("appSecret") or "").strip() or str(account.get("appSecret") or "")
        account.update({
            "appId": str(payload.get("appId") or account.get("appId") or "").strip(),
            "appSecret": app_secret,
        })
        accounts["main"] = account
        current.update({
            "enabled": enabled,
            "setupMode": setup_mode or "manual",
            "accounts": accounts,
            "privateChatPolicy": str(payload.get("privateChatPolicy") or current.get("privateChatPolicy") or "open"),
        })
    elif channel_key == "weixin":
        current.update({
            "enabled": enabled,
            "setupMode": setup_mode or "guided",
            "pluginInstalled": bool(payload.get("pluginInstalled") if payload.get("pluginInstalled") is not None else current.get("pluginInstalled")),
            "environmentStatus": str(payload.get("environmentStatus") or current.get("environmentStatus") or "").strip(),
        })
    channels[channel_key] = current

    ui_channels = store.get("channels")
    if not isinstance(ui_channels, dict):
        ui_channels = {}
        store["channels"] = ui_channels
    ui_entry = ui_channels.get(channel_key) if isinstance(ui_channels.get(channel_key), dict) else {}
    ui_entry.update({
        "enabled": enabled,
        "setupMode": setup_mode or current.get("setupMode") or IM_CHANNEL_SPECS[channel_key]["setupMode"],
        "createdAt": str(ui_entry.get("createdAt") or now),
        "updatedAt": now,
    })
    ui_channels[channel_key] = ui_entry
    return config, store


def _restart_gateway_after_channel_change() -> dict:
    restart = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "restart"], timeout=90)
    ready = _wait_for_gateway_ready(timeout_seconds=20)
    restart["gatewayStatus"] = ready
    return restart


def upsert_im_channel(channel_key: str, enabled: bool, setup_mode: str, payload: dict) -> dict:
    try:
        channel_key = _normalize_im_channel_key(channel_key)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    config, store = _write_im_channel_config(channel_key, enabled, setup_mode, payload)
    backup = _write_openclaw_config(config)
    _write_im_channels_store(store)
    restart = _restart_gateway_after_channel_change()
    channel = _build_im_channel_status(channel_key, config, store)
    return {
        "ok": restart.get("ok", False),
        "message": f"{IM_CHANNEL_SPECS[channel_key]['label']} 配置已保存" if restart.get("ok", False) else f"{IM_CHANNEL_SPECS[channel_key]['label']} 已保存，但 Gateway 重载失败",
        "backupPath": str(backup),
        "channel": channel,
        "stdout": restart.get("stdout", ""),
        "stderr": restart.get("stderr", ""),
        "code": restart.get("code"),
        "executedAt": datetime.now().isoformat(timespec="seconds"),
    }


def toggle_im_channel(channel_key: str, enabled: bool) -> dict:
    try:
        channel_key = _normalize_im_channel_key(channel_key)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    config = _read_openclaw_config()
    store = _read_im_channels_store()
    channels = _ensure_channels_root(config)
    current = channels.get(channel_key)
    if not isinstance(current, dict):
        return {"ok": False, "error": "频道尚未配置"}
    current["enabled"] = bool(enabled)
    channels[channel_key] = current
    ui_channels = store.setdefault("channels", {})
    entry = ui_channels.get(channel_key) if isinstance(ui_channels.get(channel_key), dict) else {}
    entry["enabled"] = bool(enabled)
    entry["updatedAt"] = datetime.now().isoformat(timespec="seconds")
    ui_channels[channel_key] = entry
    backup = _write_openclaw_config(config)
    _write_im_channels_store(store)
    restart = _restart_gateway_after_channel_change()
    return {
        "ok": restart.get("ok", False),
        "message": f"{IM_CHANNEL_SPECS[channel_key]['label']} 已{'启用' if enabled else '停用'}" if restart.get("ok", False) else f"{IM_CHANNEL_SPECS[channel_key]['label']} 状态已更新，但 Gateway 重载失败",
        "backupPath": str(backup),
        "channel": _build_im_channel_status(channel_key, config, store),
        "stdout": restart.get("stdout", ""),
        "stderr": restart.get("stderr", ""),
        "code": restart.get("code"),
        "executedAt": datetime.now().isoformat(timespec="seconds"),
    }


def delete_im_channel(channel_key: str) -> dict:
    try:
        channel_key = _normalize_im_channel_key(channel_key)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    config = _read_openclaw_config()
    store = _read_im_channels_store()
    channels = _ensure_channels_root(config)
    existed = channel_key in channels
    channels.pop(channel_key, None)
    ui_channels = store.get("channels")
    if isinstance(ui_channels, dict):
        ui_channels.pop(channel_key, None)
    if not existed:
        return {"ok": False, "error": "频道不存在"}
    backup = _write_openclaw_config(config)
    _write_im_channels_store(store)
    restart = _restart_gateway_after_channel_change()
    return {
        "ok": restart.get("ok", False),
        "message": f"{IM_CHANNEL_SPECS[channel_key]['label']} 已删除" if restart.get("ok", False) else f"{IM_CHANNEL_SPECS[channel_key]['label']} 已删除，但 Gateway 重载失败",
        "deleted": channel_key,
        "backupPath": str(backup),
        "stdout": restart.get("stdout", ""),
        "stderr": restart.get("stderr", ""),
        "code": restart.get("code"),
        "executedAt": datetime.now().isoformat(timespec="seconds"),
    }


def test_im_channel(channel_key: str, payload: dict) -> dict:
    try:
        channel_key = _normalize_im_channel_key(channel_key)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    config = _read_openclaw_config()
    channels = _ensure_channels_root(config)
    merged = dict(channels.get(channel_key) or {})
    if isinstance(payload, dict):
        if channel_key == "feishu":
            accounts = merged.get("accounts") if isinstance(merged.get("accounts"), dict) else {}
            account = accounts.get("main") if isinstance(accounts.get("main"), dict) else {}
            account.update({
                "appId": str(payload.get("appId") or account.get("appId") or "").strip(),
                "appSecret": str(payload.get("appSecret") or account.get("appSecret") or "").strip(),
                "domain": str(payload.get("domain") or account.get("domain") or "feishu"),
                "botName": str(payload.get("botName") or account.get("botName") or "").strip(),
            })
            accounts["main"] = account
            merged["accounts"] = accounts
            merged["defaultAccount"] = "main"
        elif channel_key == "qqbot":
            accounts = merged.get("accounts") if isinstance(merged.get("accounts"), dict) else {}
            account = accounts.get("main") if isinstance(accounts.get("main"), dict) else {}
            account.update({
                "appId": str(payload.get("appId") or account.get("appId") or "").strip(),
                "appSecret": str(payload.get("appSecret") or account.get("appSecret") or "").strip(),
            })
            accounts["main"] = account
            merged["accounts"] = accounts
            if payload.get("privateChatPolicy") is not None:
                merged["privateChatPolicy"] = str(payload.get("privateChatPolicy") or "open")
        else:
            merged.update(payload)
    checks = _channel_checks(channel_key, merged)
    ok = all(item.get("ok") for item in checks if item.get("key") not in {"plugin"})
    return {
        "ok": ok,
        "message": "检查通过" if ok else "仍有未完成项",
        "checks": checks,
        "executedAt": datetime.now().isoformat(timespec="seconds"),
    }


def _read_chat_store() -> dict:
    path = _chat_sessions_path()
    if not path.exists():
        return {"sessions": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("sessions"), list):
            return data
    except Exception:
        pass
    return {"sessions": []}


def _write_chat_store(payload: dict) -> None:
    path = _chat_sessions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _load_task_rows() -> list[dict]:
    path = data_dir() / "tasks_source.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _task_chat_session_id(task: dict) -> str:
    source_meta = task.get("sourceMeta") if isinstance(task.get("sourceMeta"), dict) else {}
    template_params = task.get("templateParams") if isinstance(task.get("templateParams"), dict) else {}
    for payload in (source_meta, template_params):
        value = str(payload.get("chatSessionId") or "").strip()
        if value:
            return value
    return ""


def _task_completion_notice(task: dict) -> str:
    task_id = str(task.get("id") or "").strip()
    title = str(task.get("title") or "").strip() or "任务"
    output = str(task.get("resolvedOutput") or task.get("output") or "").strip()
    lines = [
        f"任务 {task_id} 已完成。",
        f"事项：{title}",
        "交付已回收到侧边栏“交付归档”。",
    ]
    if output:
        lines.append(f"交付物：{output}")
    return "\n".join(lines).strip()


def _sync_chat_task_notifications(store: dict) -> bool:
    sessions = store.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        return False
    tasks = _load_task_rows()
    changed = False
    tasks_by_session: dict[str, list[dict]] = {}
    for task in tasks:
        session_id = _task_chat_session_id(task)
        if not session_id:
            continue
        if str((task.get("sourceMeta") or {}).get("flowMode") or "").strip().lower() not in {"light", "full"}:
            continue
        if str(task.get("state") or "").strip() != "Done":
            continue
        tasks_by_session.setdefault(session_id, []).append(task)

    for session in sessions:
        session_id = str(session.get("id") or "").strip()
        if not session_id:
            continue
        related = tasks_by_session.get(session_id) or []
        if not related:
            continue
        notification_map = session.get("taskNotifications")
        if not isinstance(notification_map, dict):
            notification_map = {}
            session["taskNotifications"] = notification_map
        messages = session.get("messages")
        if not isinstance(messages, list):
            messages = []
            session["messages"] = messages
        for task in sorted(related, key=lambda item: str(item.get("updatedAt") or "")):
            task_id = str(task.get("id") or "").strip()
            version = str(task.get("updatedAt") or task.get("state") or "")
            if notification_map.get(task_id) == version:
                continue
            messages.append(
                {
                    "id": f"task-done-{task_id}-{version.replace(':', '').replace('.', '').replace('-', '')[:20]}",
                    "role": "assistant",
                    "content": _task_completion_notice(task),
                    "createdAt": datetime.now().isoformat(timespec="seconds"),
                    "meta": {
                        "taskId": task_id,
                        "taskCompletion": True,
                        "flowMode": str((task.get("sourceMeta") or {}).get("flowMode") or "").strip(),
                    },
                    "error": False,
                }
            )
            notification_map[task_id] = version
            session["updatedAt"] = datetime.now().isoformat(timespec="seconds")
            changed = True
    return changed


def _chat_session_summary(session: dict) -> dict:
    messages = session.get("messages") if isinstance(session.get("messages"), list) else []
    preview = ""
    if messages:
        for item in reversed(messages):
            if item.get("role") == "assistant" and str(item.get("content") or "").strip():
                preview = str(item.get("content") or "").strip()
                break
        if not preview:
            preview = str(messages[-1].get("content") or "").strip()
    return {
        "id": session.get("id"),
        "title": session.get("title") or "新对话",
        "createdAt": session.get("createdAt"),
        "updatedAt": session.get("updatedAt"),
        "lastMessage": preview[:160],
        "messageCount": len(messages),
    }


def _chat_session_detail(session: dict) -> dict:
    detail = dict(session)
    detail.update(_chat_session_summary(session))
    detail["messages"] = session.get("messages") if isinstance(session.get("messages"), list) else []
    detail["pendingAttachments"] = session.get("pendingAttachments") if isinstance(session.get("pendingAttachments"), list) else []
    return detail


def _sanitize_attachment_name(name: str) -> str:
    base = Path(str(name or "attachment")).name.strip() or "attachment"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", base)


def _guess_attachment_kind(filename: str, content_type: str = "") -> str:
    ext = Path(filename).suffix.lower()
    guessed_type = content_type or mimetypes.guess_type(filename)[0] or ""
    if guessed_type.startswith("image/") or ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"}:
        return "image"
    return "document"


def _extract_attachment_text(path: Path, limit: int = 6000) -> str:
    ext = path.suffix.lower()
    def _finalize(raw: str) -> str:
        compact = re.sub(r"\n\s*\n+", "\n", str(raw or "")).strip()
        if len(compact) > limit:
            compact = compact[:limit] + "\n...[已截断]"
        return compact

    def _strip_xml(xml: str) -> str:
        raw = re.sub(r"</w:p>|</a:p>|</row>|</si>|</text:p>", "\n", xml)
        raw = re.sub(r"<[^>]+>", "", raw)
        return raw

    def _extract_zip_xml(*members: str) -> str:
        try:
            with zipfile.ZipFile(path) as archive:
                chunks: list[str] = []
                for name in members:
                    if name.endswith("*"):
                        prefix = name[:-1]
                        matched = sorted(item for item in archive.namelist() if item.startswith(prefix))
                    else:
                        matched = [name] if name in archive.namelist() else []
                    for member in matched:
                        chunks.append(_strip_xml(archive.read(member).decode("utf-8", errors="ignore")))
        except Exception:
            return ""
        return _finalize("\n".join(item for item in chunks if item))

    def _extract_textutil() -> str:
        if ext not in _TEXTUTIL_EXTENSIONS:
            return ""
        try:
            result = subprocess.run(
                ["/usr/bin/textutil", "-convert", "txt", "-stdout", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return ""
        if result.returncode != 0:
            return ""
        return _finalize(result.stdout)

    def _extract_mdls() -> str:
        try:
            result = subprocess.run(
                ["/usr/bin/mdls", "-raw", "-name", "kMDItemTextContent", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return ""
        if result.returncode != 0:
            return ""
        stdout = (result.stdout or "").strip()
        if not stdout or stdout == "(null)":
            return ""
        if stdout.startswith('"') and stdout.endswith('"'):
            stdout = stdout[1:-1]
        stdout = stdout.replace("\\n", "\n")
        return _finalize(stdout)

    def _extract_pdf_via_pdfkit() -> str:
        if ext != ".pdf":
            return ""
        escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
        script = (
            "import Foundation; import PDFKit; "
            f'let url = URL(fileURLWithPath: "{escaped}"); '
            'if let doc = PDFDocument(url: url) { print(doc.string ?? "") }'
        )
        env = os.environ.copy()
        env["CLANG_MODULE_CACHE_PATH"] = "/tmp/swift-module-cache"
        try:
            result = subprocess.run(
                ["/usr/bin/swift", "-e", script],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        except Exception:
            return ""
        if result.returncode != 0:
            return ""
        return _finalize(result.stdout)

    if ext == ".docx":
        text = _extract_zip_xml("word/document.xml", "word/header*.xml", "word/footer*.xml")
        if text:
            return text
    if ext == ".xlsx":
        text = _extract_zip_xml("xl/sharedStrings.xml", "xl/worksheets/*")
        if text:
            return text
    if ext == ".pptx":
        text = _extract_zip_xml("ppt/slides/*")
        if text:
            return text
    if ext not in TEXT_ATTACHMENT_EXTENSIONS:
        text = _extract_textutil() or _extract_mdls() or _extract_pdf_via_pdfkit()
        return text
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            raw = path.read_text(encoding="gb18030")
        except Exception:
            return _extract_textutil() or _extract_mdls() or _extract_pdf_via_pdfkit()
    except Exception:
        return _extract_textutil() or _extract_mdls() or _extract_pdf_via_pdfkit()
    return _finalize(raw)


def upload_chat_attachments(session_id: str, files: list[dict]) -> dict:
    if not files:
        return {"ok": False, "error": "没有可上传的文件"}

    with _CHAT_LOCK:
        store = _read_chat_store()
        sessions = store.setdefault("sessions", [])
        session = next((item for item in sessions if item.get("id") == session_id), None)
        if not session:
            return {"ok": False, "error": f"未找到会话: {session_id}"}

        upload_dir = _chat_uploads_dir() / session_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        pending = session.get("pendingAttachments")
        if not isinstance(pending, list):
            pending = []
            session["pendingAttachments"] = pending

        uploaded: list[dict] = []
        now = datetime.now().isoformat(timespec="seconds")

        for item in files:
            filename = _sanitize_attachment_name(str(item.get("filename") or "attachment"))
            content = item.get("content") or b""
            content_type = str(item.get("contentType") or "")
            attachment_id = f"att-{uuid.uuid4().hex[:12]}"
            stored_name = f"{attachment_id}_{filename}"
            target = upload_dir / stored_name
            target.write_bytes(content)
            text_excerpt = _extract_attachment_text(target)
            attachment = {
                "id": attachment_id,
                "name": filename,
                "path": str(target),
                "size": len(content),
                "contentType": content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
                "kind": _guess_attachment_kind(filename, content_type),
                "uploadedAt": now,
                "textExcerpt": text_excerpt,
            }
            pending.append(attachment)
            uploaded.append(attachment)

        session["updatedAt"] = now
        _write_chat_store(store)

    return {
        "ok": True,
        "session": _chat_session_detail(session),
        "attachments": uploaded,
        "count": len(uploaded),
        "message": "附件已上传",
    }


def remove_chat_attachment(session_id: str, attachment_id: str) -> dict:
    attachment_id = str(attachment_id or "").strip()
    if not attachment_id:
        return {"ok": False, "error": "attachmentId 不能为空"}

    with _CHAT_LOCK:
        store = _read_chat_store()
        sessions = store.setdefault("sessions", [])
        session = next((item for item in sessions if item.get("id") == session_id), None)
        if not session:
            return {"ok": False, "error": f"未找到会话: {session_id}"}

        pending = session.get("pendingAttachments")
        if not isinstance(pending, list):
            pending = []
            session["pendingAttachments"] = pending

        removed = next((item for item in pending if str(item.get("id") or "") == attachment_id), None)
        if not removed:
            return {"ok": False, "error": "未找到待删除附件"}

        session["pendingAttachments"] = [item for item in pending if str(item.get("id") or "") != attachment_id]
        session["updatedAt"] = datetime.now().isoformat(timespec="seconds")
        _write_chat_store(store)

    target = Path(str(removed.get("path") or ""))
    try:
        if target.exists():
            target.unlink()
    except Exception:
        pass

    return {
        "ok": True,
        "session": _chat_session_detail(session),
        "removedAttachmentId": attachment_id,
        "message": "附件已删除",
    }


def list_chat_sessions() -> dict:
    with _CHAT_LOCK:
        store = _read_chat_store()
        if _sync_chat_task_notifications(store):
            _write_chat_store(store)
    sessions = store.get("sessions", [])
    ordered = sorted(sessions, key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
    return {
        "ok": True,
        "sessions": [_chat_session_summary(item) for item in ordered],
        "count": len(ordered),
    }


def get_chat_session(session_id: str) -> dict:
    with _CHAT_LOCK:
        store = _read_chat_store()
        if _sync_chat_task_notifications(store):
            _write_chat_store(store)
    for session in store.get("sessions", []):
        if session.get("id") == session_id:
            return {"ok": True, "session": _chat_session_detail(session)}
    return {"ok": False, "error": f"未找到会话: {session_id}"}


def create_chat_session(title: str = "") -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    session = {
        "id": f"chat-{uuid.uuid4().hex[:12]}",
        "title": str(title or "").strip() or "新对话",
        "createdAt": now,
        "updatedAt": now,
        "messages": [],
    }
    with _CHAT_LOCK:
        store = _read_chat_store()
        sessions = store.setdefault("sessions", [])
        sessions.append(session)
        _write_chat_store(store)
    return {"ok": True, "session": _chat_session_detail(session)}


def _render_attachment_lines(prefix: str, attachments: list[dict]) -> list[str]:
    lines: list[str] = []
    for att in attachments:
        name = str(att.get("name") or "附件")
        kind = "图片" if att.get("kind") == "image" else "文档"
        path = str(att.get("path") or "")
        size = att.get("size")
        lines.append(f"{prefix}{kind}: {name}")
        if path:
            lines.append(f"{prefix}路径: {path}")
        if isinstance(size, int) and size > 0:
            lines.append(f"{prefix}大小: {size} bytes")
        excerpt = str(att.get("textExcerpt") or "").strip()
        if excerpt:
            lines.append(f"{prefix}摘录:\n{excerpt}")
    return lines


def _chat_prompt_from_history(session: dict, user_message: str, current_attachments: list[dict] | None = None) -> str:
    history = session.get("messages") if isinstance(session.get("messages"), list) else []
    recent = history[-10:]
    current_attachments = current_attachments or []
    lines = [
        "你正在 RaccoonClaw-OSS 的“对话”页中，以总裁办身份直接回复用户。",
        "",
        "1. 如果用户提出了明确的任务需求（如写文章、分析、调研、拆解等），必须首先调用相应工具进行建单、分派或状态同步。",
        "2. 严禁在未确认任务已成功录入看板（即未执行相关 scripts 命令）的情况下，仅凭话术安抚用户。",
        "3. 建单时，必须使用内部 Agent ID（如 brand_content, planning），回复用户时请使用中文部门名。",
        "4. 如果用户上传了附件，请优先查看系统提供的‘摘录’部分，它已为你解析了核心大纲。",
        "对外回复时，禁止暴露任何内部 Agent ID、脚本名或终端命令。",
        "禁止向用户提及任何内部 Agent ID 或内部脚本名。",
        "如果需要提到团队，只能使用中文部门名，例如“总裁办”“产品规划部”“评审质控部”“交付运营部”。",
        "如果用户问当前可调用的团队，只回答中文部门名，不要让用户运行 openclaw agents list 或其他终端命令。",
        "",
        "会话历史（按时间顺序）：",
    ]
    if not recent:
        lines.append("（无历史）")
    else:
        for item in recent:
            role = "用户" if item.get("role") == "user" else "总裁办"
            raw_content = str(item.get("content") or "").strip()
            content = raw_content if role == "用户" else _strip_runtime_diagnostics(raw_content)
            if not content:
                content = "（无文字内容）"
            lines.append(f"{role}: {content}")
            attachments = item.get("attachments") if isinstance(item.get("attachments"), list) else []
            if attachments:
                lines.extend(_render_attachment_lines(f"{role}附件 - ", attachments))
    lines.extend(
        [
            "",
            "当前用户消息：",
            user_message.strip() or "（无文字内容，仅发送附件）",
        "",
        ]
    )
    if current_attachments:
        lines.append("当前消息附件：")
        lines.extend(_render_attachment_lines("", current_attachments))
        lines.append("")
    lines.append("请直接回复当前用户，不要输出多余的系统说明。")
    return "\n".join(lines)


def _derive_chat_title(text: str) -> str:
    compact = " ".join(str(text or "").strip().split())
    if not compact:
        return "新对话"
    return compact[:24] + ("…" if len(compact) > 24 else "")


def _compact_chat_meta(meta: dict) -> dict:
    if not isinstance(meta, dict):
        return {}
    agent_meta = meta.get("agentMeta") if isinstance(meta.get("agentMeta"), dict) else {}
    compact = {
        "durationMs": meta.get("durationMs"),
        "aborted": meta.get("aborted"),
        "sessionId": agent_meta.get("sessionId"),
        "provider": agent_meta.get("provider"),
        "model": agent_meta.get("model"),
    }
    usage = agent_meta.get("usage")
    if isinstance(usage, dict):
        compact["usage"] = {
            "input": usage.get("input"),
            "output": usage.get("output"),
            "total": usage.get("total"),
        }
    return {key: value for key, value in compact.items() if value not in (None, "", {})}


def _sanitize_user_facing_runtime_text(text: str) -> str:
    sanitized = _strip_runtime_diagnostics(text) or str(text or "")
    replacements = {
        'Gateway agent failed; falling back to embedded:': 'Gateway 通道调用失败，已回退到本地直连：',
        'gateway connect failed:': 'Gateway 连接失败：',
        'No API key found for provider "anthropic"': '未找到 Anthropic 提供商的 API Key',
    }
    for source, target in replacements.items():
        sanitized = sanitized.replace(source, target)
    sanitized = re.sub(
        r'Unknown agent id "([^"]+)"',
        lambda match: f'未知{AGENT_ID_DISPLAY_ALIASES.get(match.group(1), "Agent")} Agent',
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
        r'Configure auth for this agent \(openclaw agents add <id>\) or copy auth-profiles\.json from the [^.]+\.',
        '请为总裁办配置模型认证，或复制已有认证文件到总裁办 Agent 目录。',
        sanitized,
    )
    sanitized = re.sub(
        r'/agents/chief_of_staff/agent/auth-profiles\.json',
        '/agents/总裁办/agent/auth-profiles.json',
        sanitized,
    )
    sanitized = re.sub(
        r'lane=session:agent:chief_of_staff:chief_of_staff',
        'lane=session:agent:总裁办:总裁办',
        sanitized,
    )
    sanitized = re.sub(
        r'lane=chief_of_staff',
        'lane=总裁办',
        sanitized,
    )
    for internal_id, display_label in AGENT_ID_DISPLAY_ALIASES.items():
        sanitized = re.sub(
            rf'(?<![A-Za-z0-9_]){re.escape(internal_id)}(?![A-Za-z0-9_])',
            display_label,
            sanitized,
        )
    sanitized = re.sub(
        r'`?openclaw agents list`?',
        'OpenClaw 的 Agent 列表',
        sanitized,
    )
    for display_label in sorted(set(AGENT_ID_DISPLAY_ALIASES.values()), key=len, reverse=True):
        sanitized = sanitized.replace(f'{display_label}（{display_label}）', display_label)
        sanitized = sanitized.replace(f'{display_label}({display_label})', display_label)
    return sanitized


def _resolve_chief_of_staff_agent_id() -> str:
    candidates = ["chief_of_staff"]
    def has_auth(agent_id: str) -> bool:
        path = OPENCLAW_CFG.parent / "agents" / agent_id / "agent" / "auth-profiles.json"
        return path.exists() and path.stat().st_size > 2
    try:
        result = _run_toolbox_command(
            [SETTINGS.openclaw_bin, "agents", "list"],
            timeout=20,
            output_limit=None,
        )
        output = "\n".join(
            part for part in [result.get("stdout") or "", result.get("stderr") or ""]
            if str(part).strip()
        ).strip()
        if output:
            runtime_ids: list[str] = []
            for raw_line in output.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or line.lower().startswith("id ") or line == "Agents:":
                    continue
                if line.startswith("- "):
                    agent_id = line[2:].split()[0].strip()
                else:
                    agent_id = line.split()[0].strip()
                if agent_id and agent_id not in runtime_ids:
                    runtime_ids.append(agent_id)
            for candidate in candidates:
                if candidate in runtime_ids and has_auth(candidate):
                    return candidate
            for candidate in candidates:
                if candidate in runtime_ids:
                    return candidate
    except Exception:
        pass
    for candidate in candidates:
        if has_auth(candidate):
            return candidate
    return "chief_of_staff"


def _analyze_chat_route(message: str) -> dict | None:
    try:
        scripts_root = ROOT / "scripts"
        if str(scripts_root) not in sys.path:
            sys.path.insert(0, str(scripts_root))
        importlib.invalidate_caches()

        if "intake_guard" in sys.modules:
            importlib.reload(sys.modules["intake_guard"])
        else:
            importlib.import_module("intake_guard")

        if "chief_of_staff_council" in sys.modules:
            council_module = importlib.reload(sys.modules["chief_of_staff_council"])
        else:
            council_module = importlib.import_module("chief_of_staff_council")

        analyze_with_council = getattr(council_module, "analyze_with_council", None)
        if not callable(analyze_with_council):
            return None

        result = analyze_with_council(message)
        return result if isinstance(result, dict) else None
    except Exception:
        return None


def _task_creation_should_fallback(error_text: str) -> bool:
    text = str(error_text or "").strip()
    if not text:
        return False
    fallback_markers = (
        "标题过短",
        "不是有效任务",
        "任务标题不能为空",
        "不像是正式任务",
    )
    return any(marker in text for marker in fallback_markers)


def _normalize_chat_attachment_payload(items: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "id": str(item.get("id") or "").strip(),
            "name": str(item.get("name") or "").strip(),
            "path": str(item.get("path") or "").strip(),
            "kind": str(item.get("kind") or "").strip(),
            "contentType": str(item.get("contentType") or "").strip(),
            "uploadedAt": str(item.get("uploadedAt") or "").strip(),
            "textExcerpt": str(item.get("textExcerpt") or "").strip(),
        })
    return [item for item in normalized if item.get("path") or item.get("name")]


def _should_inherit_recent_attachments(content: str) -> bool:
    text = str(content or "").strip()
    if not text:
        return False
    markers = (
        "进一步处理",
        "继续处理",
        "接着处理",
        "继续写",
        "改成",
        "写成",
        "扩写",
        "润色",
        "基于这个",
        "基于刚才",
        "按刚才",
        "按上面",
        "按这个",
        "根据这个",
        "根据刚才",
    )
    return any(marker in text for marker in markers)


def _inherit_recent_user_attachments(session: dict, content: str) -> list[dict]:
    if not _should_inherit_recent_attachments(content):
        return []
    history = session.get("messages") if isinstance(session.get("messages"), list) else []
    for item in reversed(history[:-1] if history else history):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        attachments = item.get("attachments") if isinstance(item.get("attachments"), list) else []
        normalized = _normalize_chat_attachment_payload(attachments)
        if normalized:
            return normalized
    return []


def _normalize_chat_text_brief(content: str, limit: int = 6000) -> str:
    text = re.sub(r"\s+\n", "\n", str(content or "").strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > limit:
        text = text[:limit].rstrip() + "\n...[已截断]"
    return text


def send_chat_message(session_id: str, content: str) -> dict:
    content = str(content or "").strip()

    with _CHAT_LOCK:
        store = _read_chat_store()
        sessions = store.setdefault("sessions", [])
        session = next((item for item in sessions if item.get("id") == session_id), None)
        if not session:
            return {"ok": False, "error": f"未找到会话: {session_id}"}
        pending_attachments = session.get("pendingAttachments") if isinstance(session.get("pendingAttachments"), list) else []
        if not content and not pending_attachments:
            return {"ok": False, "error": "消息不能为空"}
        prompt = _chat_prompt_from_history(session, content, pending_attachments)

        now = datetime.now().isoformat(timespec="seconds")
        if not session.get("messages"):
            session["title"] = _derive_chat_title(content or (pending_attachments[0].get("name") if pending_attachments else "新对话"))
        session.setdefault("messages", []).append(
            {
                "id": f"msg-{uuid.uuid4().hex[:12]}",
                "role": "user",
                "content": content,
                "createdAt": now,
                "attachments": pending_attachments,
            }
        )
        session["pendingAttachments"] = []
        session["updatedAt"] = now
        _write_chat_store(store)

    assistant_text = ""
    meta = {}
    completed = {"ok": True, "stdout": "", "stderr": "", "message": "", "code": 0}

    council = _analyze_chat_route(content)
    should_run_runtime = True
    council_classification = str((council or {}).get("classification") or "").strip()
    council_flow_mode = str((council or {}).get("flowMode") or "").strip()
    should_create_task = bool(council) and council_classification not in {"", "direct_reply"} and council_flow_mode in {"light", "full"}
    if should_create_task:
        dispatch_org = str(council.get("dispatchOrg") or council.get("recommendedOrg") or "总裁办").strip()
        target_dept = str(council.get("recommendedOrg") or dispatch_org).strip()
        official = _official_for_org(dispatch_org if council_flow_mode == "full" else target_dept or dispatch_org)
        title = str(council.get("titleHint") or "").strip() or content[:80].strip()
        if len(title) < 10:
            title = f"处理事项：{content[:24].strip()}".strip()
        attachment_payload = _normalize_chat_attachment_payload(pending_attachments)
        if not attachment_payload:
            attachment_payload = _inherit_recent_user_attachments(session, content)
        task_result = create_task(
            title=title,
            org="总裁办",
            official=official,
            priority="normal",
            template_id="",
            params={
                "chatSessionId": session_id,
                "rawRequest": content,
                "userBrief": _normalize_chat_text_brief(content),
                "chatAttachments": attachment_payload,
                "chatAttachmentCount": len(attachment_payload),
                "routeMode": str(council.get("routeMode") or "").strip(),
                "flowMode": council_flow_mode,
                "flowSummary": str(council.get("flowSummary") or "").strip(),
                "dispatchOrg": dispatch_org,
                "dispatchAgent": str(council.get("dispatchAgent") or "").strip(),
                "requiredStages": list(council.get("requiredStages") or []),
                "skipPlanning": bool(council.get("skipPlanning")),
                "skipReview": bool(council.get("skipReview")),
            },
            target_dept=target_dept,
            mode_id="",
            flow_mode=council_flow_mode,
        )
        if task_result.get("ok"):
            should_run_runtime = False
            task_id = str(task_result.get("taskId") or "").strip()
            if council_flow_mode == "direct":
                assistant_text = (
                    f"已收到需求，已创建任务 {task_id}。\n"
                    f"当前由总裁办按直办流程处理，直接安排给{dispatch_org or '总裁办'}执行。"
                ).strip()
            elif council_flow_mode == "light":
                assistant_text = (
                    f"已收到需求，已创建任务 {task_id}。\n"
                    f"当前由总裁办按轻流程直派至{dispatch_org}执行，跳过产品规划部与评审质控部。"
                ).strip()
            else:
                assistant_text = (
                    f"已收到需求，已创建任务 {task_id}。\n"
                    f"当前将由总裁办按完整流程推进，下一步交给产品规划部处理。"
                ).strip()
            meta = {
                "taskId": task_id,
                "routeMode": str(council.get("routeMode") or council_classification or "create_task"),
                "flowMode": council_flow_mode,
                "dispatchOrg": dispatch_org,
                "dispatchAgent": council.get("dispatchAgent") or "",
                "createdBy": "chat_frontdoor",
            }
        else:
            task_error = str(task_result.get("error") or task_result.get("message") or "任务创建失败")
            if _task_creation_should_fallback(task_error):
                should_run_runtime = True
                meta = {
                    **meta,
                    "routeMode": "fallback_chat",
                    "routingFallbackReason": task_error,
                }
            else:
                should_run_runtime = False
                completed = {
                    "ok": False,
                    "stdout": "",
                    "stderr": task_error,
                    "message": "任务创建失败",
                    "code": 1,
                }
                assistant_text = f"已收到需求，但创建正式任务失败：{completed['stderr']}"
    if should_run_runtime:
        target_agent_id = _resolve_chief_of_staff_agent_id()
        runtime_prompt = prompt
        if council_flow_mode == "direct" and council_classification == "direct_handle":
            runtime_prompt = (
                f"{prompt}\n\n"
                "补充约束：总裁办已完成分诊，当前请求属于 direct 直办任务。\n"
                "禁止建单，禁止转交其他部门，禁止只回复“已创建任务”。\n"
                "请直接给出最终答案或结果。"
            )
        completed = _run_toolbox_command(
            [
                SETTINGS.openclaw_bin,
                "--no-color",
                "agent",
                "--agent",
                target_agent_id,
                "--message",
                runtime_prompt,
                "--json",
            ],
            timeout=600,
            output_limit=None,
        )

        if completed.get("ok"):
            try:
                parsed = json.loads(completed.get("stdout") or "{}")
                payloads = (((parsed.get("result") or {}).get("payloads")) or [])
                assistant_text = "\n\n".join(
                    str(item.get("text") or "").strip()
                    for item in payloads
                    if str(item.get("text") or "").strip()
                ).strip()
                meta = _compact_chat_meta(((parsed.get("result") or {}).get("meta")) or {})
            except Exception:
                assistant_text = _extract_runtime_payload_text(completed.get("stdout") or "") or completed.get("stdout") or ""
        if AGENT_ID_DISPLAY_ALIASES.get(target_agent_id, target_agent_id) != "总裁办":
            meta = {
                **meta,
                "runtimeAgentId": target_agent_id,
                "agentFallback": "总裁办兼容回退",
            }
        if not assistant_text:
            assistant_text = (
                _extract_runtime_payload_text(completed.get("stderr") or "")
                or completed.get("stderr")
                or completed.get("message")
                or "未收到有效回复"
            )
        assistant_text = _sanitize_user_facing_runtime_text(assistant_text)

    with _CHAT_LOCK:
        store = _read_chat_store()
        sessions = store.setdefault("sessions", [])
        session = next((item for item in sessions if item.get("id") == session_id), None)
        if not session:
            return {"ok": False, "error": f"未找到会话: {session_id}"}
        now = datetime.now().isoformat(timespec="seconds")
        session.setdefault("messages", []).append(
            {
                "id": f"msg-{uuid.uuid4().hex[:12]}",
                "role": "assistant",
                "content": assistant_text,
                "createdAt": now,
                "meta": meta,
                "error": not completed.get("ok"),
            }
        )
        session["updatedAt"] = now
        _write_chat_store(store)
        return {
            "ok": completed.get("ok", False),
            "session": _chat_session_detail(session),
            "message": "发送成功" if completed.get("ok") else "发送失败",
            "stdout": _sanitize_user_facing_runtime_text(completed.get("stdout", "")),
            "stderr": _sanitize_user_facing_runtime_text(completed.get("stderr", "")),
            "code": completed.get("code"),
        }


def _read_app_bundle_version(app_path: Path) -> str:
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.exists():
        return ""
    try:
        with info_plist.open("rb") as fh:
            data = plistlib.load(fh)
        return str(data.get("CFBundleShortVersionString") or "").strip()
    except Exception:
        return ""


def _detect_wechat_environment() -> dict:
    app_candidates = [
        Path("/Applications/WeChat.app"),
        Path.home() / "Applications" / "WeChat.app",
    ]
    app_path = next((path for path in app_candidates if path.exists()), None)
    version = _read_app_bundle_version(app_path) if app_path else ""
    required_version = "8.0.70"
    node_path = shutil.which("node") or ""
    npx_path = shutil.which("npx") or ""
    return {
        "supported": True,
        "requiredVersion": required_version,
        "installCommand": " ".join(WECHAT_INSTALL_COMMAND),
        "appInstalled": bool(app_path),
        "appPath": str(app_path) if app_path else "",
        "version": version,
        "versionOk": bool(version) and version == required_version,
        "nodeAvailable": bool(node_path),
        "npxAvailable": bool(npx_path),
        "message": "按向导检查微信 8.0.70 与微信 ClawBot 插件后，再执行安装命令。",
    }


def _build_feishu_status(config: dict) -> dict:
    channels = config.get("channels") if isinstance(config.get("channels"), dict) else {}
    feishu = channels.get("feishu") if isinstance(channels.get("feishu"), dict) else {}
    accounts = feishu.get("accounts") if isinstance(feishu.get("accounts"), dict) else {}
    default_account = str(feishu.get("defaultAccount") or "main")
    account = accounts.get(default_account) if isinstance(accounts.get(default_account), dict) else {}
    configured = bool(account.get("appId")) and bool(account.get("appSecret"))
    return {
        "mode": "app_credentials",
        "configured": configured,
        "defaultAccount": default_account,
        "appId": str(account.get("appId") or ""),
        "domain": str(account.get("domain") or feishu.get("domain") or "feishu"),
        "botName": str(account.get("botName") or ""),
        "dmPolicy": str(feishu.get("dmPolicy") or "pairing"),
        "groupPolicy": str(feishu.get("groupPolicy") or "open"),
        "connectionMode": str(feishu.get("connectionMode") or "websocket"),
    }


def connect_feishu_channel(app_id: str, app_secret: str, domain: str = "feishu", bot_name: str = "") -> dict:
    app_id = str(app_id or "").strip()
    app_secret = str(app_secret or "").strip()
    domain = str(domain or "feishu").strip().lower() or "feishu"
    bot_name = str(bot_name or "").strip()

    if not app_id.startswith("cli_"):
        return {"ok": False, "error": "飞书 App ID 格式无效，应以 cli_ 开头"}
    if domain not in {"feishu", "lark"}:
        return {"ok": False, "error": "domain 仅支持 feishu 或 lark"}

    config = _read_openclaw_config()
    channels = config.setdefault("channels", {})
    if not isinstance(channels, dict):
        channels = {}
        config["channels"] = channels
    feishu = channels.get("feishu")
    if not isinstance(feishu, dict):
        feishu = {}
    accounts = feishu.get("accounts")
    if not isinstance(accounts, dict):
        accounts = {}
    default_account = str(feishu.get("defaultAccount") or "main")
    account = accounts.get(default_account)
    if not isinstance(account, dict):
        account = {}

    existing_secret = str(account.get("appSecret") or "")
    if not app_secret:
        app_secret = existing_secret
    if not app_secret:
        return {"ok": False, "error": "飞书 App Secret 不能为空"}

    account["appId"] = app_id
    account["appSecret"] = app_secret
    account["domain"] = domain
    if bot_name:
        account["botName"] = bot_name
    elif account.get("botName") is None:
        account["botName"] = ""

    accounts[default_account] = account
    feishu["enabled"] = True
    feishu["defaultAccount"] = default_account
    feishu["accounts"] = accounts
    feishu["domain"] = domain
    feishu["dmPolicy"] = str(feishu.get("dmPolicy") or "pairing")
    feishu["groupPolicy"] = str(feishu.get("groupPolicy") or "open")
    feishu["connectionMode"] = str(feishu.get("connectionMode") or "websocket")
    channels["feishu"] = feishu

    backup = _write_openclaw_config(config)
    restart = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "restart"], timeout=90)
    status = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "status"], timeout=20)
    return {
        "ok": restart.get("ok", False),
        "message": "飞书配置已保存并重启 Gateway" if restart.get("ok") else "飞书配置已保存，但 Gateway 重启失败",
        "backupPath": str(backup),
        "requestedAction": "feishu_connect",
        "action": restart.get("action", ""),
        "stdout": restart.get("stdout", ""),
        "stderr": restart.get("stderr", ""),
        "code": restart.get("code"),
        "executedAt": datetime.now().isoformat(timespec="seconds"),
        "gatewayStatus": status,
        "feishu": _build_feishu_status(config),
    }


def _run_toolbox_command(cmd: list[str], timeout: int = 120, output_limit: int | None = 4000) -> dict:
    normalized_cmd = _normalize_toolbox_cmd(cmd)
    try:
        completed = subprocess.run(
            normalized_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_toolbox_env(),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return {
            "ok": False,
            "action": " ".join(normalized_cmd),
            "message": "执行超时",
            "stdout": stdout[-output_limit:] if output_limit else stdout,
            "stderr": stderr[-output_limit:] if output_limit else stderr,
            "code": None,
            "executedAt": datetime.now().isoformat(timespec="seconds"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "action": " ".join(normalized_cmd),
            "message": str(exc),
            "stdout": "",
            "stderr": "",
            "code": None,
            "executedAt": datetime.now().isoformat(timespec="seconds"),
        }

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    return {
        "ok": completed.returncode == 0,
        "action": " ".join(normalized_cmd),
        "message": "执行成功" if completed.returncode == 0 else "执行失败",
        "stdout": stdout[-output_limit:] if output_limit else stdout,
        "stderr": stderr[-output_limit:] if output_limit else stderr,
        "code": completed.returncode,
        "executedAt": datetime.now().isoformat(timespec="seconds"),
    }


def _wait_for_gateway_ready(timeout_seconds: int = 20) -> dict:
    deadline = datetime.now().timestamp() + timeout_seconds
    last = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "status"], timeout=20)
    while datetime.now().timestamp() < deadline:
        last = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "status"], timeout=20)
        if last.get("ok"):
            return last
        time.sleep(1)
    return last


def get_toolbox_status() -> dict:
    gateway = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "status"], timeout=20)
    config = _read_openclaw_config()
    base = data_dir()
    sync_status_path = base / "sync_status.json"
    agent_config_path = base / "agent_config.json"
    live_status_path = base / "live_status.json"

    def _read_sync_status() -> dict:
        try:
            payload = json.loads(sync_status_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    sync_status = _read_sync_status()
    runtime_sync_ok = bool(sync_status.get("ok")) if "ok" in sync_status else sync_status_path.exists()
    runtime_sync_message = str(sync_status.get("detail") or sync_status.get("message") or "").strip()
    if not runtime_sync_message:
        runtime_sync_message = "Runtime 已同步" if runtime_sync_ok else "等待同步 Runtime"

    agent_config_ok = agent_config_path.exists()
    live_status_ok = live_status_path.exists()

    return {
        "ok": True,
        "gateway": gateway,
        "doctor": {
            "ok": None,
            "message": "未执行",
            "action": f"{SETTINGS.openclaw_bin} doctor",
            "stdout": "",
            "stderr": "",
            "code": None,
        },
        "runtimeSync": {
            "ok": runtime_sync_ok,
            "message": runtime_sync_message,
            "action": "sync_from_openclaw_runtime",
            "stdout": "",
            "stderr": "",
            "code": 0 if runtime_sync_ok else None,
        },
        "syncAgentConfig": {
            "ok": agent_config_ok,
            "message": "Agent 配置已同步" if agent_config_ok else "等待同步 Agent 配置",
            "action": "sync_agent_config",
            "stdout": "",
            "stderr": "",
            "code": 0 if agent_config_ok else None,
        },
        "refreshLiveStatus": {
            "ok": live_status_ok,
            "message": "任务状态已刷新" if live_status_ok else "等待刷新任务状态",
            "action": "refresh_live_status",
            "stdout": "",
            "stderr": "",
            "code": 0 if live_status_ok else None,
        },
        "checkedAt": datetime.now().isoformat(timespec="seconds"),
        "feishu": _build_feishu_status(config),
        "wechat": _detect_wechat_environment(),
    }


def run_toolbox_action(action: str) -> dict:
    server = load_legacy_server_module()
    scripts_dir = server.SCRIPTS
    if action == "gateway_status":
        result = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "status"], timeout=20)
    elif action == "gateway_install":
        result = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "install"], timeout=180)
        if result.get("ok"):
            gateway_status = _wait_for_gateway_ready(timeout_seconds=30)
            result["gatewayStatus"] = gateway_status
            if gateway_status.get("ok"):
                result["message"] = "Gateway 安装完成并已就绪"
            else:
                result["message"] = "Gateway 安装已执行，但仍未就绪"
    elif action == "gateway_restart":
        result = _run_toolbox_command([SETTINGS.openclaw_bin, "gateway", "restart"], timeout=60)
        gateway_status = _wait_for_gateway_ready(timeout_seconds=20)
        result["gatewayStatus"] = gateway_status
        if result.get("ok") and gateway_status.get("ok"):
            result["message"] = "Gateway 已重启并恢复就绪"
        elif result.get("ok"):
            result["ok"] = False
            result["message"] = "Gateway 重启命令已执行，但服务未恢复就绪"
    elif action == "doctor":
        result = _run_toolbox_command([SETTINGS.openclaw_bin, "doctor"], timeout=45)
    elif action == "doctor_fix":
        result = _run_toolbox_command([SETTINGS.openclaw_bin, "doctor", "--fix"], timeout=180)
    elif action == "runtime_sync":
        result = _run_embedded_script("sync_from_openclaw_runtime") if _desktop_mode_enabled() else _run_toolbox_command(["python3", str(scripts_dir / "sync_from_openclaw_runtime.py")], timeout=90)
    elif action == "refresh_live_status":
        result = _run_embedded_script("refresh_live_data") if _desktop_mode_enabled() else _run_toolbox_command(["python3", str(scripts_dir / "refresh_live_data.py")], timeout=90)
    elif action == "sync_agent_config":
        result = _run_embedded_script("sync_agent_config") if _desktop_mode_enabled() else _run_toolbox_command(["python3", str(scripts_dir / "sync_agent_config.py")], timeout=60)
    elif action == "reset_entry_sessions":
        result = _run_embedded_script("reset_entry_sessions") if _desktop_mode_enabled() else _run_toolbox_command(["python3", str(scripts_dir / "reset_entry_sessions.py")], timeout=60)
    elif action == "reset_agent_sessions":
        result = _run_embedded_script("reset_agent_sessions") if _desktop_mode_enabled() else _run_toolbox_command(["python3", str(scripts_dir / "reset_agent_sessions.py")], timeout=60)
    elif action == "wechat_env_check":
        env = _detect_wechat_environment()
        lines = [
            f"WeChat.app: {'yes' if env['appInstalled'] else 'no'}",
            f"version: {env['version'] or 'unknown'}",
            f"required: {env['requiredVersion']}",
            f"node: {'yes' if env['nodeAvailable'] else 'no'}",
            f"npx: {'yes' if env['npxAvailable'] else 'no'}",
            f"install command: {env['installCommand']}",
        ]
        result = {
            "ok": bool(env["appInstalled"]) and bool(env["nodeAvailable"]) and bool(env["npxAvailable"]),
            "action": "wechat_env_check",
            "message": "微信环境可继续安装" if bool(env["appInstalled"]) and bool(env["nodeAvailable"]) and bool(env["npxAvailable"]) else "微信环境未就绪，请先补齐缺失项",
            "stdout": "\n".join(lines),
            "stderr": "",
            "code": 0 if bool(env["appInstalled"]) and bool(env["nodeAvailable"]) and bool(env["npxAvailable"]) else 1,
            "executedAt": datetime.now().isoformat(timespec="seconds"),
            "wechat": env,
        }
    elif action == "wechat_install":
        result = _run_toolbox_command(WECHAT_INSTALL_COMMAND, timeout=600)
        result["wechat"] = _detect_wechat_environment()
    else:
        return {"ok": False, "error": f"不支持的动作: {action}"}

    result["requestedAction"] = action
    return result

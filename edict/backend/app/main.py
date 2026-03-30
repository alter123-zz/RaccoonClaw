"""RaccoonClaw-OSS backend entrypoint.

Lifespan 管理：
- startup: 连接 Redis Event Bus, 初始化数据库
- shutdown: 关闭连接

路由：
- /api/tasks — 任务 CRUD
- /api/agents — Agent 信息
- /api/events — 事件查询
- /api/admin — 管理操作
- /ws — WebSocket 实时推送
"""

import asyncio
import datetime as dt
import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .services.event_bus import get_event_bus
from .services.legacy_dashboard import ensure_live_status_fresh
from .services.legacy_server_bridge import run_due_scheduled_jobs as legacy_run_due_scheduled_jobs
from .services.legacy_server_bridge import scheduler_scan as legacy_scheduler_scan
from .services.runtime_bootstrap import get_desktop_startup_status
from .api import tasks, agents, events, admin, websocket, dashboard
from .api import legacy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("raccoonclaw")


def write_startup_probe(message: str) -> None:
    raw = os.environ.get("OPENCLAW_DESKTOP_STARTUP_LOG", "").strip()
    if not raw:
        return
    try:
        target = Path(raw).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().isoformat(timespec="seconds")
        with target.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} pid={os.getpid()} {message}\n")
    except Exception:
        pass


def resolve_dashboard_dist() -> Path:
    override = os.environ.get("EDICT_DASHBOARD_DIST", "").strip()
    if override:
        return Path(override).expanduser()

    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "dashboard" / "dist"

    return Path(__file__).parents[3] / "dashboard" / "dist"


DASHBOARD_DIST = resolve_dashboard_dist()
write_startup_probe(
    f"app.main loaded dashboard_dist={DASHBOARD_DIST} exists={DASHBOARD_DIST.exists()}"
)


def _desktop_mode_enabled() -> bool:
    return os.environ.get("OPENCLAW_APP_MODE", "").strip().lower() == "desktop"


def _desktop_setup_block_response() -> HTMLResponse | None:
    if not _desktop_mode_enabled():
        return None

    status = get_desktop_startup_status()
    if status.get("ready"):
        return None

    summary = str(status.get("summary") or "RaccoonClaw-OSS 尚未就绪")
    detail = str(status.get("detail") or "请返回启动向导，先完成 OpenClaw 与组织配置检查。")
    output = str(status.get("statusOutput") or "")
    recommended_action = str(status.get("recommendedAction") or "").strip()
    provision_allowed = bool(status.get("cliInstalled")) and recommended_action != "install_cli"
    action_label = "一键初始化并导入 OpenClaw 工作台" if provision_allowed else "请先安装 OpenClaw CLI"
    escaped_output = output.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>RaccoonClaw-OSS Setup Required</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #f4f7fb;
        color: #20314c;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
      }}
      .card {{
        width: min(720px, calc(100vw - 48px));
        padding: 28px;
        border: 1px solid #d7e1f1;
        border-radius: 24px;
        background: rgba(255,255,255,0.96);
        box-shadow: 0 24px 60px rgba(47,63,112,0.12);
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: 28px;
      }}
      p {{
        margin: 0;
        color: #6f819d;
        line-height: 1.7;
      }}
      .summary {{
        margin-top: 18px;
        padding: 14px 16px;
        border-radius: 14px;
        background: rgba(47,110,241,0.08);
        font-weight: 700;
      }}
      .actions {{
        margin-top: 20px;
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        align-items: center;
      }}
      .btn {{
        appearance: none;
        border: 0;
        border-radius: 999px;
        padding: 12px 18px;
        background: #2f6ef1;
        color: white;
        font-size: 14px;
        font-weight: 700;
        cursor: pointer;
      }}
      .btn[disabled] {{
        cursor: not-allowed;
        opacity: 0.45;
      }}
      .hint {{
        color: #6f819d;
        font-size: 13px;
      }}
      pre {{
        margin: 18px 0 0;
        padding: 14px;
        border-radius: 14px;
        background: #eef3fb;
        border: 1px solid #d7e1f1;
        font-size: 12px;
        line-height: 1.5;
        white-space: pre-wrap;
        overflow: auto;
      }}
    </style>
  </head>
  <body>
    <main class="card">
      <h1>RaccoonClaw-OSS 尚未完成启动</h1>
      <p>工作台已被后端保护。请回到启动向导先完成 OpenClaw、Gateway 和组织配置检查，再进入工作台。</p>
      <div class="summary" id="startup-summary">{summary}</div>
      <p style="margin-top: 12px;" id="startup-detail">{detail}</p>
      <div class="actions">
        <button class="btn" id="bootstrap-btn" {"disabled" if not provision_allowed else ""}>{action_label}</button>
        <span class="hint" id="startup-hint">{"工作台将尝试自动初始化 OpenClaw、导入组织配置并重启 Gateway。" if provision_allowed else "当前机器还未安装 OpenClaw CLI，无法继续初始化。"}</span>
      </div>
      {"<pre id='startup-output'>" + escaped_output + "</pre>" if escaped_output else "<pre id='startup-output' hidden></pre>"}
    </main>
    <script>
      const button = document.getElementById('bootstrap-btn');
      const summary = document.getElementById('startup-summary');
      const detail = document.getElementById('startup-detail');
      const hint = document.getElementById('startup-hint');
      const output = document.getElementById('startup-output');
      const defaultLabel = {action_label!r};

      function setOutput(text) {{
        const body = String(text || '').trim();
        if (!body) {{
          output.hidden = true;
          output.textContent = '';
          return;
        }}
        output.hidden = false;
        output.textContent = body;
      }}

      async function refreshStartupStatus() {{
        const resp = await fetch('/api/desktop/startup-status', {{ cache: 'no-store' }});
        const data = await resp.json();
        summary.textContent = data.summary || 'RaccoonClaw-OSS 尚未就绪';
        detail.textContent = data.detail || '';
        if (data.statusOutput) {{
          setOutput(data.statusOutput);
        }}
        if (data.ready) {{
          hint.textContent = '启动检查已通过，正在进入工作台…';
          window.location.href = '/';
        }}
      }}

      async function provisionRuntime() {{
        if (button.disabled) return;
        button.disabled = true;
        button.textContent = '初始化中…';
        hint.textContent = '正在初始化 OpenClaw、导入组织配置并等待 Gateway 就绪。';
        setOutput('正在执行 OpenClaw 初始化，请稍候…');
        try {{
          const resp = await fetch('/api/bootstrap/provision', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
          }});
          const data = await resp.json();
          summary.textContent = data.summary || '初始化已执行';
          detail.textContent = data.detail || '';
          setOutput(data.output || '');
          if (data.ok) {{
            hint.textContent = '初始化完成，正在重新检查工作台状态…';
            await refreshStartupStatus();
            return;
          }}
          hint.textContent = '初始化已执行，但工作台仍未就绪。请查看输出后重试。';
        }} catch (error) {{
          hint.textContent = '初始化请求失败，请检查后端日志。';
          setOutput(String(error || 'unknown error'));
        }} finally {{
          button.disabled = {str(not provision_allowed).lower()};
          button.textContent = defaultLabel;
        }}
      }}

      if (button) {{
        button.addEventListener('click', provisionRuntime);
      }}
    </script>
  </body>
</html>"""
    return HTMLResponse(content=html, status_code=503)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    settings = get_settings()
    desktop_mode = os.environ.get("OPENCLAW_APP_MODE", "").strip().lower() == "desktop"
    write_startup_probe(
        f"lifespan begin desktop_mode={desktop_mode} redis_url={settings.redis_url} port={settings.port}"
    )
    log.info(f"🦝 RaccoonClaw-OSS backend starting on port {settings.port}...")
    app.state.event_bus_connected = False
    scheduler_task: asyncio.Task | None = None
    scheduled_jobs_task: asyncio.Task | None = None
    live_sync_task: asyncio.Task | None = None
    news_task: asyncio.Task | None = None

    # 连接 Event Bus
    bus = None
    try:
        write_startup_probe("event_bus connect begin")
        bus = await get_event_bus()
        app.state.event_bus_connected = True
        write_startup_probe("event_bus connect ok")
        log.info("✅ Event Bus connected")
    except Exception as exc:
        write_startup_probe(f"event_bus connect degraded: {exc}")
        log.warning("⚠️ Event Bus unavailable, starting in degraded mode: %s", exc)

    try:
        live_payload = ensure_live_status_fresh()
        repair_report = live_payload.get("repairReport") if isinstance(live_payload, dict) else {}
        if isinstance(repair_report, dict) and repair_report:
            write_startup_probe(
                "live status warmup ok "
                f"changed={repair_report.get('changed', 0)} "
                f"migrated={repair_report.get('migratedOutputs', 0)} "
                f"blocked={repair_report.get('blockedTasks', 0)}"
            )
        else:
            write_startup_probe("live status warmup ok")
    except Exception as exc:
        write_startup_probe(f"live status warmup degraded: {exc}")
        log.warning("⚠️ Live status warmup failed during startup: %s", exc)

    async def scheduler_loop():
        interval = max(15, int(settings.scheduler_scan_interval_seconds or 60))
        threshold = max(30, int(settings.stall_threshold_sec or 180))
        await asyncio.sleep(3)
        while True:
            try:
                if desktop_mode:
                    startup = get_desktop_startup_status()
                    if not startup.get("ready"):
                        await asyncio.sleep(interval)
                        continue
                result = legacy_scheduler_scan(threshold)
                count = int((result or {}).get("count") or 0)
                if count:
                    log.info("🧭 Scheduler auto-scan handled %s action(s)", count)
            except Exception as exc:
                log.warning("⚠️ Scheduler auto-scan failed: %s", exc)
            await asyncio.sleep(interval)

    async def scheduled_jobs_loop():
        interval = max(15, min(int(settings.heartbeat_interval_sec or 30), 60))
        await asyncio.sleep(4)
        while True:
            try:
                if desktop_mode:
                    startup = get_desktop_startup_status()
                    if not startup.get("ready"):
                        await asyncio.sleep(interval)
                        continue
                result = legacy_run_due_scheduled_jobs()
                count = int((result or {}).get("count") or 0)
                if count:
                    log.info("⏰ Scheduled jobs loop triggered %s task(s)", count)
            except Exception as exc:
                log.warning("⚠️ Scheduled jobs loop failed: %s", exc)
            await asyncio.sleep(interval)

    async def live_sync_loop():
        interval = max(15, min(int(settings.heartbeat_interval_sec or 30), 60))
        await asyncio.sleep(5)
        while True:
            try:
                ensure_live_status_fresh()
            except Exception as exc:
                log.warning("⚠️ Live status auto-sync failed: %s", exc)
            await asyncio.sleep(interval)

    scheduler_task = asyncio.create_task(scheduler_loop())
    scheduled_jobs_task = asyncio.create_task(scheduled_jobs_loop())
    live_sync_task = asyncio.create_task(live_sync_loop())
    write_startup_probe("lifespan ready")

    yield

    # 清理
    if scheduler_task is not None:
        scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_task
    if scheduled_jobs_task is not None:
        scheduled_jobs_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduled_jobs_task
    if live_sync_task is not None:
        live_sync_task.cancel()
        with suppress(asyncio.CancelledError):
            await live_sync_task
    if bus is not None:
        await bus.close()
    write_startup_probe("lifespan shutdown complete")
    log.info("RaccoonClaw-OSS backend shutdown complete")


app = FastAPI(
    title="RaccoonClaw-OSS",
    description="事件驱动的 AI Agent 公司协作平台",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — 开发环境允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(websocket.router, tags=["websocket"])
app.include_router(legacy.router, prefix="/api/tasks", tags=["legacy"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])

assets_dir = DASHBOARD_DIST / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="dashboard-assets")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "engine": "raccoonclaw-oss",
        "eventBusConnected": bool(getattr(app.state, "event_bus_connected", False)),
    }


@app.get("/healthz")
async def healthz():
    return await health()


@app.get("/api")
async def api_root():
    return {
        "name": "RaccoonClaw-OSS API",
        "version": "2.0.0",
        "endpoints": {
            "tasks": "/api/tasks",
            "agents": "/api/agents",
            "dashboard": "/api/live-status",
            "events": "/api/events",
            "admin": "/api/admin",
            "websocket": "/ws",
            "health": "/health",
        },
    }


@app.get("/", include_in_schema=False)
async def dashboard_root():
    blocked = _desktop_setup_block_response()
    if blocked is not None:
        return blocked
    index_path = DASHBOARD_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return await api_root()


@app.get("/{full_path:path}", include_in_schema=False)
async def dashboard_fallback(full_path: str):
    if full_path.startswith("api/") or full_path in {"health", "healthz", "ws"}:
        raise HTTPException(status_code=404, detail="Not found")

    target = DASHBOARD_DIST / full_path
    if target.is_file():
        return FileResponse(target)

    blocked = _desktop_setup_block_response()
    if blocked is not None:
        return blocked

    index_path = DASHBOARD_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")

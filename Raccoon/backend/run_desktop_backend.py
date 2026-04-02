from __future__ import annotations

import datetime as dt
import os
import sys
import traceback
from pathlib import Path

import uvicorn


def _startup_log_path() -> Path | None:
    raw = os.environ.get("OPENCLAW_DESKTOP_STARTUP_LOG", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _write_startup_log(message: str) -> None:
    target = _startup_log_path()
    if target is None:
        return
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().isoformat(timespec="seconds")
        with target.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} pid={os.getpid()} {message}\n")
    except Exception:
        pass


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "7891"))
    _write_startup_log(
        "entry host="
        f"{host} port={port} app_mode={os.environ.get('OPENCLAW_APP_MODE', '')} "
        f"openclaw_home={os.environ.get('OPENCLAW_HOME', '')} executable={sys.executable}"
    )
    try:
        from app.main import app as fastapi_app

        _write_startup_log("imported app.main successfully")
        _write_startup_log("starting uvicorn")
        uvicorn.run(fastapi_app, host=host, port=port, log_level="info")
        _write_startup_log("uvicorn exited normally")
    except Exception:
        _write_startup_log("fatal startup exception")
        _write_startup_log(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()

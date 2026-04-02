# Dashboard Service Runner

The dashboard backend listens on `127.0.0.1:7891`. The core start command stays the same across platforms:

```bash
bash scripts/run_single_backend.sh
```

For long-running usage, wrap that command with an OS-native service runner instead of depending on a terminal tab.

## macOS

Install as a LaunchAgent:

```bash
bash scripts/install_dashboard_launchagent.sh
```

Useful commands:

```bash
launchctl print gui/$(id -u)/ai.openclaw.edict-dashboard
tail -f ~/.openclaw/logs/edict-7891.stderr.log
bash scripts/uninstall_dashboard_launchagent.sh
```

## Windows

Use the PowerShell wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_single_backend.ps1
```

For background operation, use one of:

- Task Scheduler
- NSSM (Non-Sucking Service Manager)
- WinSW

Recommended pattern:

1. Create or activate `.venv-backend`
2. Point the service runner to `scripts/run_single_backend.ps1`
3. Keep `HOST=127.0.0.1` and `PORT=7891`
4. Route stdout/stderr to log files

This keeps the application logic cross-platform while letting each OS use its own service manager.

# Single Backend Cutover

## Goal

Use the FastAPI backend as the primary dashboard server, while temporarily reusing the file-backed logic from `dashboard/server.py`.

## What Works Now

- FastAPI serves the built dashboard page from `dashboard/dist/`.
- FastAPI exposes the dashboard read APIs:
  - `/api/live-status`
  - `/api/agent-config`
  - `/api/officials-stats`
  - `/api/model-change-log`
  - `/api/last-result`
  - `/api/agents-status`
  - `/api/task-activity/{taskId}`
  - `/api/scheduler-state/{taskId}`
  - `/api/skill-content/{agentId}/{skillName}`
  - `/api/remote-skills-list`
- FastAPI also exposes the dashboard write APIs by bridging to the legacy implementation:
  - `/api/create-task`
  - `/api/task-action`
  - `/api/review-action`
  - `/api/advance-state`
  - `/api/archive-task`
  - `/api/task-todos`
  - `/api/set-model`
  - `/api/agent-wake`
  - `/api/scheduler-scan`
  - `/api/scheduler-retry`
  - `/api/scheduler-escalate`
  - `/api/scheduler-rollback`
  - `/api/add-skill`
  - `/api/add-remote-skill`
  - `/api/update-remote-skill`
  - `/api/remove-remote-skill`

## Start Command

```bash
cd "/Users/altergoo/Documents/New project/RaccoonClaw-OSS"
bash scripts/run_single_backend.sh
```

Then open:

- `http://127.0.0.1:8000`
- `http://127.0.0.1:7891`

The script prefers the project virtual environment at `.venv-backend/` and falls back to system `python3` only when that virtual environment does not exist.

## Fresh Clone Note

In this workspace, the backend dependencies have already been installed into `.venv-backend/`. On a fresh clone, install the backend stack from `edict/backend/requirements.txt` before using the single-backend start script.

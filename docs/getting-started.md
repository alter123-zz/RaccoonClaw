# Getting Started

## 1. Prerequisites

- OpenClaw CLI installed
- Python 3.10+
- Node.js 18+ if you want to rebuild the frontend

You do **not** need an existing `~/.openclaw` runtime. Community edition prefers a repo-local runtime.

## 2. Copy the environment template

```bash
cp .env.example .env
```

Recommended defaults:

- `OPENCLAW_HOME=./.openclaw`
- `RACCOONCLAW_DATA_PROFILE=clean`
- keep optional features disabled on first boot

If you want seeded example tasks and archive cards, switch:

```bash
RACCOONCLAW_DATA_PROFILE=demo
```

## 3. Initialize OpenClaw for this repo

If `.openclaw/openclaw.json` does not exist yet, run:

```bash
OPENCLAW_HOME="$PWD/.openclaw" openclaw setup
```

This creates a repo-local runtime instead of writing to your global home runtime.

## 4. Install the workspace

```bash
chmod +x install.sh
./install.sh
```

The installer will:

- source `.env` when present
- create canonical workspaces under `OPENCLAW_HOME`
- register canonical agents in `OPENCLAW_HOME/openclaw.json`
- seed a `clean` or `demo` profile
- build the frontend when Node.js is available
- run an initial sync

## 5. Start the backend

```bash
bash scripts/run_single_backend.sh
```

Open:

```text
http://127.0.0.1:7891
```

## 5B. Optional: Start with Docker Compose

Docker is an optional enhancement for reproducible demos. The primary community path is still:

- local install
- repo-local `.openclaw`
- `install.sh`
- `scripts/run_single_backend.sh`

If you specifically want a containerized run, use:

```bash
docker compose up --build
```

This path will:

- build the frontend inside the image
- install backend dependencies inside the container
- seed a clean or demo runtime into `/app/.openclaw`
- start the same FastAPI entrypoint used by local development

The compose file persists runtime data in the local `./.openclaw/` directory.

## 6. Runtime and data layout

Community edition uses two separate roots:

- repo-local runtime: `./.openclaw/`
- repo-local fallback data: `./data/`

Normal runs should read from `./.openclaw/workspace-chief_of_staff/data/`.

## 7. Troubleshooting

### Backend starts but UI is blank

Rebuild the frontend:

```bash
cd edict/frontend
npm install
npm run build
```

### Gateway/OpenClaw is not ready

Community edition can run without enabling the toolbox page. If you explicitly enabled gateway features, check:

```bash
openclaw gateway status
openclaw gateway restart
```

### Need to reset to a clean state

```bash
python3 scripts/seed_runtime_data.py --profile clean --repo-dir "$PWD" --openclaw-home "$PWD/.openclaw" --force
python3 scripts/refresh_live_data.py
```

### Need demo tasks and archive cards

```bash
python3 scripts/seed_runtime_data.py --profile demo --repo-dir "$PWD" --openclaw-home "$PWD/.openclaw" --force
python3 scripts/refresh_live_data.py
```

### Need to refresh runtime data manually

```bash
python3 scripts/sync_agent_config.py
python3 scripts/refresh_live_data.py
```

### Docker build works but the page has no data

Check whether your `.env` overrides the profile or feature flags. Then rebuild:

```bash
docker compose down
docker compose up --build
```

### Need release validation before publishing

Use the checklist in [docs/releasing.md](./releasing.md).

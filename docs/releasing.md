# Releasing Community Edition

This document is the release checklist for the open-source community edition of RaccoonClaw-OSS.

## Goal

Before tagging a release, verify that:

- a new user can boot the project from a clean checkout
- old `JJC-*` data still opens and migrates safely
- optional features stay off by default unless explicitly enabled
- the UI build, backend regressions, migration regressions, and browser smoke all pass

## Release Checklist

### 1. Clean runtime boot

- Copy [/.env.example](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/.env.example) to `.env`
- Confirm community defaults:
  - `OPENCLAW_HOME=./.openclaw`
  - `RACCOONCLAW_DATA_PROFILE=clean`
  - `RACCOONCLAW_ENABLE_IM_CHANNELS=false`
  - `RACCOONCLAW_ENABLE_TOOLBOX=false`
  - `RACCOONCLAW_ENABLE_SCHEDULED_TASKS=true`
  - `RACCOONCLAW_ENABLE_AUTOMATION_MIRRORS=false`
- Run:

```bash
python3 scripts/seed_runtime_data.py --profile clean --repo-dir "$PWD" --openclaw-home "$PWD/.openclaw" --force
```

### 2. Demo fixture boot

- Run:

```bash
python3 scripts/seed_runtime_data.py --profile demo --repo-dir "$PWD" --openclaw-home "$PWD/.openclaw" --force
```

- Confirm demo creates:
  - one completed deliverable
  - one scheduled job
  - a valid `.openclaw/openclaw.json`

### 3. Backend regressions

- Run:

```bash
.venv-backend/bin/python -m unittest discover -s tests -p 'test_*.py'
```

- Pay special attention to:
  - `test_desktop_regressions.py`
  - `test_migration_regressions.py`
  - `test_scheduled_jobs_regressions.py`
  - `test_seed_runtime_data.py`
  - `test_chat_attachment_regressions.py`

### 4. Frontend build

- Run:

```bash
cd edict/frontend
npm run build
```

- Confirm build output lands in [dashboard/dist](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/dashboard/dist)

### 5. Browser smoke

- Start backend:

```bash
bash scripts/run_single_backend.sh
```

- In another shell run:

```bash
python3 scripts/ui_smoke.py
```

- Confirm smoke covers:
  - chat attachment upload/remove
  - scheduled task cards hide automation mirror IDs
  - memorial search returns results

### 6. Optional Docker smoke

Docker is not a release blocker for the community edition baseline. Run this only if you intend to maintain the container path:

```bash
docker compose build
docker compose up -d
```

- Confirm:
  - [http://127.0.0.1:7891](http://127.0.0.1:7891) opens
  - `.openclaw/` is created locally
  - `/healthz` returns `ok`
  - clean profile does not include private historical data

### 7. Docs sync

- Update if needed:
  - [README.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/README.md)
  - [README_EN.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/README_EN.md)
  - [docs/getting-started.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/docs/getting-started.md)
  - [docs/community-edition.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/docs/community-edition.md)

- Confirm docs still match:
  - env defaults
  - feature flag defaults
  - Docker startup steps, if you still advertise them
  - known limits

### 8. Release gate

Do not cut a release if any of these are true:

- clean boot still reads personal `~/.openclaw` state by default
- migration tests fail for old `JJC-*` tasks
- scheduled tasks can re-arm after cancellation
- memorial search cannot find old archived work
- chat attachments fail in browser smoke
- the local install path is broken even if Docker still works

## Release procedure

When all release checks are green, cut the release in this order:

1. Update [CHANGELOG.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/CHANGELOG.md)
2. Copy [docs/release-notes-template.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/docs/release-notes-template.md) into a new versioned note under `docs/releases/`
3. Confirm [README.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/README.md), [README_EN.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/README_EN.md), [SUPPORT.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/SUPPORT.md), and [SECURITY.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/SECURITY.md) still match the intended support contract
4. Commit the release preparation
5. Create the tag
6. Publish the GitHub release using the versioned note

Suggested commands:

```bash
git add .
git commit -m "release: prepare vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

If you have not yet replaced placeholder repository URLs in [/.github/ISSUE_TEMPLATE/config.yml](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/.github/ISSUE_TEMPLATE/config.yml), do that before the first public release.

## Release output

A release is ready when all checks above are green and the release notes clearly call out:

- core features included
- optional features disabled by default
- experimental features, if any
- known limits that still remain

Use these files when cutting the release:

- [CHANGELOG.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/CHANGELOG.md)
- [docs/release-notes-template.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/docs/release-notes-template.md)
- [docs/releases/0.1.0.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/docs/releases/0.1.0.md) as the initial baseline example

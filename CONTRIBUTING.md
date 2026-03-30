# Contributing

## Scope

This repository is the clean OSS line for RaccoonClaw. Changes should keep the repository free of legacy organizational naming and legacy project storytelling.

## Local workflow

```bash
cp .env.example .env
chmod +x install.sh
./install.sh
bash scripts/run_single_backend.sh
```

Frontend build:

```bash
cd edict/frontend
npm install
npm run build
```

## Community baseline rules

- keep repo-local runtime support working (`OPENCLAW_HOME=./.openclaw`)
- do not reintroduce hardcoded `/Users/...` paths
- do not make optional features default-on without updating docs and tests
- keep `clean` and `demo` seed profiles valid

## Pull requests

- keep canonical agent ids only
- prefer targeted patches over broad rewrites
- include verification notes
- remove or update user-facing docs when behavior changes
- update [CHANGELOG.md](/Users/altergoo/Documents/New%20project/RaccoonClaw-OSS/CHANGELOG.md) and release docs when a user-facing baseline changes

## Required checks

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
cd edict/frontend && npm install && npm run build
python3 scripts/seed_runtime_data.py --profile demo --repo-dir "$PWD" --openclaw-home "$PWD/.openclaw" --force
python3 scripts/ui_smoke.py
```

## Basic syntax checks

```bash
python3 -m py_compile dashboard/server.py
python3 -m py_compile scripts/*.py
bash -n install.sh
bash -n scripts/run_single_backend.sh
```

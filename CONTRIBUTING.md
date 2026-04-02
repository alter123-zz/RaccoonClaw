# Contributing

## Scope

This repository is the clean OSS line for RaccoonClaw. Changes should keep the repository free of legacy organizational naming and legacy project storytelling.

## Local workflow

```bash
chmod +x install.sh
./install.sh
bash scripts/run_single_backend.sh
```

Frontend build:

```bash
cd Raccoon/frontend
npm install
npm run build
```

## Pull requests

- keep canonical agent ids only
- prefer targeted patches over broad rewrites
- include verification notes
- remove or update user-facing docs when behavior changes

## Basic checks

```bash
python3 -m py_compile dashboard/server.py
python3 -m py_compile scripts/*.py
cd Raccoon/frontend && npm run build
```

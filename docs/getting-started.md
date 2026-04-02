# Getting Started

## Prerequisites

- OpenClaw installed and initialized
- Python 3.9+
- Node.js 18+ if you want to rebuild the frontend

## Install

```bash
git clone <your-repo-url> RaccoonClaw-OSS
cd RaccoonClaw-OSS
chmod +x install.sh
./install.sh
```

The installer will:

- create canonical OpenClaw workspaces
- register canonical agents in `~/.openclaw/openclaw.json`
- initialize local data files
- build the frontend when Node.js is available
- run an initial sync

## Run

```bash
bash scripts/run_single_backend.sh
```

Open:

```text
http://127.0.0.1:7891
```

## Messaging channels

Use `chief_of_staff` as the entry agent when connecting channels:

```bash
openclaw channels list
openclaw channels add --type feishu --agent chief_of_staff
```

## Common tasks

- create and route work from the task board
- talk to the chief of staff from the chat page
- review archived deliverables in `交付归档`
- configure models and skills per agent

## Troubleshooting

Check gateway:

```bash
openclaw gateway status
openclaw gateway restart
```

Run one-off sync:

```bash
python3 scripts/sync_agent_config.py
python3 scripts/refresh_live_data.py
```

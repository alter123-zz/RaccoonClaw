# RaccoonClaw-OSS

[English](./README_EN.md) | [中文](./README.md)

RaccoonClaw-OSS is an OpenClaw-based multi-Agent workspace. It unifies task intake, triage, review, execution, and delivery archival into one observable interface, using modern organizational naming throughout.

## Features

- **Chief-of-Staff Entry**: Distinguishes casual chat, direct handling, light flow, and full flow
- **Task Board**: Create, advance, pause, cancel, and archive tasks
- **Delivery Archive**: Preserves task timelines and deliverables
- **Status Monitor**: View department, agent, blocker, and active task status
- **Model & Skill Config**: Manage models, installed skills, and built-in skills per agent
- **Daily Briefing**: Manual and scheduled collection with configurable sources

## Organization Structure

| ID | Department | Role |
|----|-----------|------|
| `chief_of_staff` | Chief of Staff | Intake & external communication |
| `planning` | Product Planning | Requirement breakdown & solution planning |
| `review_control` | Review & QA | Solution review & risk assessment |
| `delivery_ops` | Delivery Operations | Task dispatch & delivery tracking |
| `brand_content` | Brand & Content | Content creation & brand management |
| `business_analysis` | Business Analytics | Data analysis & business insights |
| `secops` | Security Operations | Security monitoring & incident response |
| `compliance_test` | Compliance Testing | Quality assurance & compliance checks |
| `engineering` | Engineering | Software development & infrastructure |
| `people_ops` | People Operations | Team coordination & resource management |

## Quick Start

### Prerequisites

- Python 3.11+
- [OpenClaw](https://github.com/openclaw/openclaw) installed and initialized

### Installation

```bash
git clone https://github.com/your-org/RaccoonClaw-OSS.git
cd RaccoonClaw-OSS
chmod +x install.sh
./install.sh
```

### Run

```bash
bash scripts/run_single_backend.sh
```

Open in browser:

```
http://127.0.0.1:7891
```

### Docker (Alternative)

```bash
docker compose up
```

## Project Structure

```
agents/          Agent personas and default configs
dashboard/       Single-backend workspace service
Raccoon/           React frontend & FastAPI bridge layer
scripts/         Install, sync, schedule, and collect scripts
shared/          Agent registry, workflow config, mode configs
skills/          Built-in skills
tests/           Regression tests
docs/            Documentation and screenshots
```

## Design Principles

- **Canonical-only**: Uses modern organizational naming exclusively
- **Observable**: Task flow, deliverables, and blockers are visible in the workspace
- **Intervenable**: Tasks can be paused, cancelled, directly dispatched, or follow the full pipeline
- **Deployable**: Built on OpenClaw, designed to run locally

## Documentation

- [Getting Started](./docs/getting-started.md) — Detailed setup guide
- [Dashboard Service](./docs/dashboard-service.md) — Architecture overview
- [Contributing](./CONTRIBUTING.md) — How to contribute

## License

[MIT](./LICENSE)

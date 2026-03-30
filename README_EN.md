# RaccoonClaw-OSS

RaccoonClaw-OSS is an OpenClaw-based multi-agent workspace focused on observable task routing, execution, and delivery. The repository now ships with a community-edition baseline meant to be runnable from a clean checkout.

## 3-Minute Local Start

```bash
cp .env.example .env
chmod +x install.sh
./install.sh
bash scripts/run_single_backend.sh
```

Open `http://127.0.0.1:7891`.

The default path is `local install + repo-local .openclaw`. Docker/Compose remains optional and is not the main community-edition entrypoint.

## What it is

- Chief-of-staff entry point for chat, direct handling, light flow, and full flow
- Task board with create / pause / cancel / archive
- Delivery archive with timeline and deliverables
- Agent status monitor
- Per-agent model and skill management

## What it is not

- Not a hosted SaaS
- Not a cloud control plane
- Not an all-features-enabled product by default

Community edition keeps only the most stable surfaces enabled by default. Optional modules such as IM channels, toolbox/gateway controls, scheduled tasks, and automation mirrors are opt-in through `.env`.

## Quick start

```bash
cp .env.example .env
chmod +x install.sh
./install.sh
bash scripts/run_single_backend.sh
```

Docker Compose is optional and not the primary community-edition path:

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:7891
```

See [docs/getting-started.md](./docs/getting-started.md) for setup details, [docs/community-edition.md](./docs/community-edition.md) for scope and feature tiers, [docs/releasing.md](./docs/releasing.md) for the release checklist, [CHANGELOG.md](./CHANGELOG.md) for version history, [SECURITY.md](./SECURITY.md) for private vulnerability reporting, and [SUPPORT.md](./SUPPORT.md) for support boundaries.

# Community Edition Scope

## What community edition optimizes for

- local-first setup
- observable task routing
- stable core workflow
- clean startup from a fresh clone
- repo-local `.openclaw` as the standard runtime root

## Core features

These are expected to work in a clean checkout and stay enabled by default:

- chat with the chief of staff
- create one-shot tasks
- direct / light / full routing
- task board and task detail modal
- delivery archive
- model configuration
- skill configuration
- task templates

## Optional advanced features

These are useful, but not enabled by default in the open-source baseline:

- IM channels
- gateway / toolbox controls
- scheduled tasks
- automation mirrors
- Docker / Compose startup path

Enable them through `.env` only after the core workflow is healthy on your machine.

## Experimental / environment-sensitive features

These depend heavily on your local OpenClaw runtime, local services, or connector credentials:

- gateway doctor / repair actions
- external IM delivery
- recurring automation fan-out
- machine-specific launch agents / cron integration

## Suitable users

- developers exploring OpenClaw-native workbenches
- teams that want a local-first multi-agent operations UI
- contributors who are comfortable running Python, Node.js, and OpenClaw locally

## Not suitable for

- teams expecting a hosted SaaS
- non-technical users who need one-click cloud onboarding
- environments where local runtime state is disallowed

## Known limits

- community edition is single-machine first
- local install is the primary supported path
- Docker is optional, not the main distribution contract
- optional features need explicit configuration
- some advanced integrations still depend on local OpenClaw capabilities and credentials
- the repository prioritizes stability over enabling every internal feature by default

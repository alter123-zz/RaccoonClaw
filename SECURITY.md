# Security Policy

## Supported scope

This repository is a local-first community edition of RaccoonClaw-OSS. Security support focuses on:

- the default local install path
- repo-local runtime state under `.openclaw`
- the enabled-by-default community baseline
- regression risks that expose local data, credentials, or unsafe task execution

Optional integrations such as IM delivery, gateway repair actions, scheduled fan-out, and Docker are best-effort unless they are part of the documented community baseline for a tagged release.

## What to report

Please report issues such as:

- local data leakage across runtime roots
- unsafe path traversal or arbitrary file access
- secret exposure in logs, UI, or deliverables
- unintended execution triggered by task intake, scheduled jobs, or automation mirrors
- privilege or environment breakout through optional tooling

## How to report

Do not open a public issue for a suspected security vulnerability.

Instead:

- prepare a minimal reproduction
- include affected version or commit
- include whether you used `clean` or `demo` seed data
- include whether optional features were enabled

Then contact the maintainer privately before public disclosure.

## Disclosure expectations

- acknowledgement target: within 7 days
- triage target: within 14 days
- fix or mitigation target: depends on severity and reproducibility

If a fix is shipped, release notes should call out the security impact and whether users need to rotate credentials, clear runtime state, or reseed `.openclaw`.

## Out of scope

The following are generally out of scope unless they create a direct issue in the default community baseline:

- problems caused by custom local OpenClaw setups outside repo-local `.openclaw`
- machine-specific launch agents, personal cron wiring, or private connector credentials
- unsupported production or hosted deployments

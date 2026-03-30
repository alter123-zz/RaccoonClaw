# Support

## Community edition support boundary

RaccoonClaw-OSS is maintained as a local-first community edition. The main supported path is:

- local install
- repo-local `.openclaw`
- documented seed profiles
- enabled-by-default community baseline

If you stay on that path, bugs and regressions are actionable. If you enable advanced features or wire the project into custom local infrastructure, support becomes best-effort.

## Best place to start

Before opening an issue, please verify:

1. You copied `.env.example` to `.env`
2. You used repo-local `OPENCLAW_HOME=./.openclaw`
3. You can reproduce on a fresh `clean` or `demo` seed
4. You are on the latest main branch or latest tagged release

## Good bug reports

Include:

- the task or page you were using
- exact reproduction steps
- whether the issue happens on `clean` seed, `demo` seed, or migrated data
- whether optional features were enabled
- screenshots or logs when relevant

Useful attachments:

- `.openclaw/workspace-chief_of_staff/data/live_status.json`
- `.openclaw/workspace-chief_of_staff/data/task_store_repair_report.json`
- browser console screenshot if it is a UI issue

## What maintainers can reasonably help with

- local startup issues on the documented path
- task routing regressions
- delivery archive/search regressions
- seed and migration bugs
- community baseline UI and API issues

## Best-effort only

- IM channel provider-specific issues
- Docker-specific issues
- machine-specific cron / launch agent issues
- custom OpenClaw runtime layouts
- private cloud or SaaS-style deployments

## Not supported

- managed hosting
- production SLAs
- custom enterprise integrations not present in this repository

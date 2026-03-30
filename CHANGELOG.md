# Changelog

All notable changes to the community edition of RaccoonClaw-OSS should be documented in this file.

The format is based on Keep a Changelog, but optimized for this repo's local-first release flow.

## [Unreleased]

### Added
- 3-minute local startup path in the top-level README.
- Community-edition release note template in `docs/release-notes-template.md`.

### Changed
- Open-source baseline is explicitly local-first with repo-local `.openclaw`.

### Fixed
- TBD

## [0.1.0] - 2026-03-30

### Added
- Community-edition baseline with local install flow, repo-local runtime seed, feature flags, release checklist, and CI coverage.

### Changed
- Docker/Compose kept as an optional enhancement instead of the primary startup path.

### Fixed
- Scheduled-task cancellation now disables the real cron job and prevents silent re-registration.
- Runtime data paths no longer default back to personal `~/.openclaw` state in the main community flow.

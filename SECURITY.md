# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in RaccoonClaw-OSS, please report it responsibly:

- **Email**: Open a GitHub Security Advisory at `Security > Advisories` in the repository
- **Do NOT** file a public issue for security vulnerabilities

We will acknowledge your report within 48 hours and provide a more detailed response within 7 days.

## Security Considerations

### Deployment

- **CORS**: In development mode, CORS allows all origins. For production, set the `CORS_ORIGINS` environment variable to restrict allowed origins (comma-separated).
- **Secret Key**: The `SECRET_KEY` environment variable must be set in production. If omitted, a random key is generated at startup (not suitable for multi-instance deployments).
- **Database**: Default uses SQLite for local development. For production, configure PostgreSQL via `POSTGRES_HOST` and related environment variables.

### API Access

The workspace API does not include built-in authentication. For production deployments, place the service behind a reverse proxy (e.g., Nginx, Caddy) with appropriate access controls.

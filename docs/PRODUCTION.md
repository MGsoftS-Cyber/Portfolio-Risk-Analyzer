# Production preparation

This is a functional first release. Subscription billing and team accounts are not included. Before public deployment: verify Docker/PostgreSQL startup and backups; enable HTTPS and COOKIE_SECURE=true; configure exact ALLOWED_ORIGINS; implement verified email/password recovery, shared rate limits for multiple workers, upload/request limits at a reverse proxy, session cleanup, monitoring, dependency security scanning and restore testing. Review market-data licensing before adding providers. The current login limiter is process-local. No bank credentials or live trading are handled.

Compose binds localhost only. Do not expose PostgreSQL directly. Keep .env and databases out of git. Use a managed secret store for production. Test every migration against the intended PostgreSQL release before deployment.

# iMixing Production Readiness

This document tracks the beta-launch engineering surface.

## Implemented in repository

- App icon endpoint and favicon/apple-touch-icon references.
- Draft public pages: Terms, Privacy, Refund, Data Retention, Early Access.
- SQLite persistence for demo credits, credit ledger, audio job metadata, users, projects, and waitlist signups.
- Initial migration in `migrations/001_initial.sql`.
- Environment-driven limits for MIDI size, audio upload size, stem count, demo credits, and queue/storage settings.
- Object-storage abstraction for local/S3/R2.
- Queue abstraction for FastAPI background tasks with Redis/RQ/Celery placeholders.
- Render blueprint with web service and worker placeholder.
- Structured JSON logs, analytics events, and Sentry DSN hook.

## Still required before paid public sales

- Replace SQLite on `/tmp` with managed PostgreSQL.
- Wire Redis/RQ or Celery for real worker isolation.
- Wire S3/R2 storage for uploads and outputs.
- Add authentication and real user accounts.
- Add payment provider, invoices, and refund automation.
- Run legal review for all draft policy pages.
- Add abuse prevention, rate limits, virus scanning, and deletion automation.

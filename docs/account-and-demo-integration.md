# Household accounts, scan automation, and demo scenes

## Account integration

The account API provides registration, login, revocable seven-day sessions, and per-household membership records. Configure a random `HOMHIVE_ACCOUNT_SIGNING_SECRET` of at least 32 characters in ignored `backend/.env`; run Alembic migrations before enabling account auth. Existing household bearer-token compatibility is retained for local tests and migration, **not** suitable for a public deployment without removal and an authorization audit.

An authenticated session is linked to a registered user and one generated household. **Load household** must successfully retrieve history before the UI shows connected status. Log out revokes the session.

## Demo library

The image picker uses static, demonstration-only assets under `frontend/public/demo-library/`. Selecting a sample uploads it into the authenticated household and invokes the real vision analysis endpoint. Public demo images must not include private household uploads. Some original variant candidates have not been individually verified for public release.

## Autonomous scan pipeline

After claim-level corroborated observations persist, the vision endpoint triggers intelligence refresh to discover tasks. The system may return zero observations or tasks where evidence is insufficient. Existing observation records are deduplicated by media ID. The full event-notification, task upsert/reconciliation, exact physical-room matching, grounded estimate, and completion-proof workflows remain in development and must not be represented as fully automated.

## Validation checklist

- Back up the database; apply `alembic upgrade head` to a disposable/test database first.
- Verify account registration/login, invalid credentials, logout and cross-household access denial.
- Verify browsing images, selecting one, reviewing independent verification results, and refreshing tasks.
- Validate existing household-token fixtures, full backend test suite, frontend typecheck and production build.
- Do not deploy publicly until rate limiting, CSRF/session design, privacy and auth migration are reviewed.

# HomHive Current State

## Implemented

The backend uses typed Pydantic domain models with deterministic services for:

- timestamped `Observation` evidence, `HouseholdState`, `ConditionSnapshot`, and `ConditionTrend`
- reactive dish/laundry task discovery with confidence thresholds and active-task deduplication
- `Task` lifecycle, deterministic `ScoredTask` ranking, and explainable decisions
- household entity candidates, conservative matching, resolution, and entity application services
- condition forecasting, `ThresholdCrossing`, `ActionDecision`, and predictive task reconciliation
- FastAPI and Strawberry GraphQL household-entity operations
- authenticated, household-scoped image upload and retrieval through FastAPI, with JPEG, PNG, and WebP validation and a 10 MiB limit

## Persistent storage

SQLAlchemy 2.x and Alembic support PostgreSQL storage for household entities, observations, tasks, and media metadata.

- `HouseholdEntityStorage`, `ObservationStorage`, and `TaskStorage` define repository behavior.
- In-memory implementations remain available for deterministic tests.
- SQLAlchemy implementations map ORM records to and from Pydantic domain models.
- Observation and task repositories isolate records by household ID.
- Observation history is loaded chronologically and replayed by `reconstruct_household_state()`.
- Tasks retain IDs, task keys, status, urgency, deadlines, source observation references, and metadata across database sessions.
- The entity API selects in-memory or SQL-backed storage using `HOMHIVE_ENTITY_STORAGE`.
- Media bytes are stored under a configured private filesystem root; PostgreSQL stores the media ID, household ID, content type, size, and timestamp.
- Media lookups use `(household_id, media_id)`; bearer authorization is checked before storage access.
- The media router is enabled only when both `HOMHIVE_MEDIA_ROOT` and `HOMHIVE_HOUSEHOLD_TOKENS` are configured. It also requires `DATABASE_URL`.
- Alembic migration head is `0004_media`.

A live PostgreSQL database has been used to verify entity access through GraphQL after application restart, observation history reconstruction, task status transitions, and sequential prevention of duplicate active tasks across Python processes. Media was also uploaded and retrieved through authenticated HTTP endpoints, with a SHA-256 match against the original image and isolation checks using two separately authenticated households. These checks exercise existing components, not a single atomic ingestion-to-planning pipeline.

## Automated tests

The latest locally reported backend regression result is:

```text
262 passed
```

The suite covers domain rules, forecasting, GraphQL behavior, repository boundaries, persisted record mappings, household isolation, lifecycle updates, history reconstruction, and media upload/retrieval, validation, authorization, and storage behavior. This is a test baseline, not a product-quality score.

## Current limitations

- Image ingestion stores and retrieves bytes but does not yet extract observations; video ingestion, frame sampling, and multimodal vision remain unimplemented.
- No Tavily runtime integration, research cache, or external-evidence persistence.
- No Nemotron/Nebius runtime integration or LangSmith/Toloka evaluation integration.
- No production Next.js PWA or complete media-to-observation-to-planning API orchestration.
- Observation and task repositories are not yet wired into a complete application-managed persistent workflow.
- No durable record of each historical task-status transition or full audit log.
- No concurrency-safe atomic deduplication across the observation-to-task workflow.
- Reactive and predictive task keys are not unified.
- No availability engine, quiet hours, calendar/email context, execution windows, or full cross-domain planning.
- Household bearer tokens are local-development credentials; user accounts, membership-based authorization, and production media storage controls are not yet implemented.

## System boundaries

Raw observations, reconstructed household state, derived condition beliefs, forecasts, action decisions, and tasks are separate concepts. Persisted observations remain the evidence source; derived beliefs can be recalculated. API/service/repository and domain/ORM boundaries remain explicit.

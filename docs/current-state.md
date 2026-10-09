# HomHive Current State

## Implemented

The backend uses typed Pydantic domain models with deterministic services for:

- timestamped `Observation` evidence, `HouseholdState`, `ConditionSnapshot`, and `ConditionTrend`
- reactive dish/laundry task discovery with confidence thresholds and active-task deduplication
- `Task` lifecycle, deterministic `ScoredTask` ranking, and explainable decisions
- household entity candidates, conservative matching, resolution, and entity application services
- condition forecasting, `ThresholdCrossing`, `ActionDecision`, and predictive task reconciliation
- FastAPI and Strawberry GraphQL household-entity operations

## Persistent storage

SQLAlchemy 2.x and Alembic support PostgreSQL storage for household entities, observations, and tasks.

- `HouseholdEntityStorage`, `ObservationStorage`, and `TaskStorage` define repository behavior.
- In-memory implementations remain available for deterministic tests.
- SQLAlchemy implementations map ORM records to and from Pydantic domain models.
- Observation and task repositories isolate records by household ID.
- Observation history is loaded chronologically and replayed by `reconstruct_household_state()`.
- Tasks retain IDs, task keys, status, urgency, deadlines, source observation references, and metadata across database sessions.
- The entity API selects in-memory or SQL-backed storage using `HOMHIVE_ENTITY_STORAGE`.
- Alembic migration head is `0003_tasks`.

A live PostgreSQL database has been used to verify entity access through GraphQL after application restart, observation history reconstruction, task status transitions, and sequential prevention of duplicate active tasks across Python processes. These checks exercise existing components, not a single atomic ingestion pipeline.

## Automated tests

The latest locally reported backend regression result is:

```text
256 passed
```

The suite covers domain rules, forecasting, GraphQL behavior, repository boundaries, persisted record mappings, household isolation, lifecycle updates, and history reconstruction. This is a test baseline, not a product-quality score.

## Current limitations

- No real photo or video ingestion, frame sampling, or multimodal vision adapter.
- No Tavily runtime integration, research cache, or external-evidence persistence.
- No Nemotron/Nebius runtime integration or LangSmith/Toloka evaluation integration.
- No production Next.js PWA or full ingestion-to-planning API orchestration.
- Observation and task repositories are not yet wired into a complete application-managed persistent workflow.
- No durable record of each historical task-status transition or full audit log.
- No concurrency-safe atomic deduplication across the observation-to-task workflow.
- Reactive and predictive task keys are not unified.
- No availability engine, quiet hours, calendar/email context, execution windows, or full cross-domain planning.

## System boundaries

Raw observations, reconstructed household state, derived condition beliefs, forecasts, action decisions, and tasks are separate concepts. Persisted observations remain the evidence source; derived beliefs can be recalculated. API/service/repository and domain/ORM boundaries remain explicit.

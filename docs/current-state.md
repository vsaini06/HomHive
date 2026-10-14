# HomHive Current State

## Implemented system

HomHive currently includes:

- typed Pydantic domain models for observations, state, entities, tasks, forecasts, decisions, and plans
- confidence- and recency-aware state aggregation with temporal history
- deterministic reactive task discovery and active-task deduplication
- deterministic task scoring and ranking
- conservative household-entity candidate matching and resolution
- condition forecasting, threshold crossing, action decisions, and predictive task reconciliation
- FastAPI application boundaries and Strawberry GraphQL entity operations
- household-scoped PostgreSQL repositories through SQLAlchemy and Alembic
- authenticated private media upload/retrieval with JPEG, PNG, and WebP validation
- Nebius MiniCPM-V-4_5 image-to-observation inference with strict evidence validation
- explicit unknown AI confidence stored as `None` / SQL `NULL`
- user confirmation that creates separate user evidence
- scene-inventory evaluation with detection-only object discovery and completeness scoring
- household intelligence refresh over persisted observations and tasks
- Tavily research with normalized evidence and durable household-scoped cache storage
- deterministic feasibility planning for time, presence, quiet-hours, and task-count constraints
- NVIDIA Nemotron planning through Nebius with strict structured-output validation and deterministic fallback
- mobile-first Next.js client for the main product loop
- Docker Compose runtime with PostgreSQL 17, FastAPI, Next.js, migrations, and persistent database/media volumes

## Persistent storage

SQLAlchemy 2.x and Alembic support PostgreSQL storage for household entities, observations, tasks, media metadata, and research cache records.

Important storage boundaries:

- observation and task access is household-scoped
- observation history remains durable and can reconstruct current household state
- derived snapshots and forecasts are recomputed rather than treated as authoritative stored truth
- media bytes live under a private media root while PostgreSQL stores media metadata
- media lookup uses both household ID and media ID
- research cache records are household-scoped
- ORM records remain separate from Pydantic domain models

The current migration head is `0006_research_cache`.

## Verified runtime behavior

The following paths have been exercised with real runtime dependencies:

- authenticated media upload and retrieval
- Nebius MiniCPM perception and observation persistence
- explicit observation confirmation
- household intelligence refresh
- Tavily live research
- NVIDIA Nemotron live planning through Nebius
- context replanning from 20 available active minutes to 5 minutes
- Docker Compose startup with PostgreSQL healthy
- Alembic migration during backend-container startup
- FastAPI `/health` returning HTTP 200
- Next.js production container returning HTTP 200

The browser scenario produced a 76% `dish_load` value, required confirmation, produced reactive and predictive work, and then generated different plans from the same stored household state as the available-time constraint changed.

## Automated verification

The current full backend regression baseline is:

```text
348 passed
```

Frontend verification also passes:

```text
npm run typecheck
npm run build
```

The test suite covers domain rules, forecasting, persistence, repository contracts, household isolation, media validation/authorization, scene evaluation, observation review, household intelligence, Tavily research/cache behavior, planning feasibility, and planning APIs. Test count is a regression metric, not a product-accuracy metric.

## Scene-completeness evaluation

A human-reviewed kitchen development set contains 59 reference entities across four scenes.

```text
Joint micro recall:       47.46%
Joint micro precision:    75.68%
Joint micro F1:           58.33%

Detection micro recall:   71.19%
Detection micro precision:72.41%
Detection micro F1:       71.79%
```

Detection-first inference improved recall by 23.73 percentage points, or 50.0% relative, and improved micro-F1 by 13.46 percentage points.

These results remain development measurements. The scorer has label/granularity limitations, the evaluation covers only four kitchen scenes, and a heavy joint request required one retry after strict output validation rejected the first response.

## Current limitations

- video ingestion and frame sampling are not implemented
- scene completeness is not yet evaluated across broad household domains
- persistent cross-image physical-entity identity remains incomplete
- reactive and predictive work can still represent the same underlying condition with different task keys
- full task-transition and plan audit history is not persisted
- concurrency-safe atomic deduplication across the complete observation-to-task workflow is not implemented
- calendar, email, richer presence, and work-status integrations are not implemented
- background job execution for long-running model/media work is not implemented
- development household bearer tokens are not production user authentication
- public production deployment is not claimed; the current deployment verification is a local Docker runtime smoke test
- LangSmith, Toloka, and Tandem are not required for the verified core flow and are not currently integrated

## System boundaries

Raw observations, derived state, forecasts, action decisions, tasks, ranking, feasibility, research evidence, and final plans remain separate concepts. External provider output is parsed and validated before it can influence stable domain state or executable work.

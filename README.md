# HomHive

HomHive is an intelligence layer for household operations.

It is designed to understand changing household conditions, discover work without requiring a person to manually create every task, forecast when conditions may become problematic, research unfamiliar situations when needed, and produce a prioritized action plan for humans or future autonomous executors.

## Product direction

```text
Phone photos / short video
        |
        v
Environmental perception
        |
        v
Structured observations
        |
        v
Household state + history
        |
        +------------------+
        |                  |
        v                  v
Reactive task discovery   Forecasting
        |                  |
        +---------+--------+
                  |
                  v
           Action decisions
                  |
                  v
             Task ranking
                  |
                  v
      Research when knowledge is missing
                  |
                  v
      Cross-domain reasoning and planning
                  |
                  v
       Human or future robot executor
```

HomHive focuses on the orchestration and reasoning layer. The MVP does not require custom sensors, permanent cameras, a custom vision model, or a physical robot.

## Current implementation

The backend implements a deterministic foundation alongside an opt-in, provider-adapted image-to-observation workflow.

Implemented:

- typed household observations and condition categories
- observation history and current household state
- confidence- and recency-aware condition snapshots
- deterministic trend detection
- reactive task discovery
- duplicate active-task prevention
- deterministic task scoring and ranking
- persistent household-entity domain models
- deterministic entity compatibility, match assessment, and resolution
- in-memory and SQL-backed household-entity repositories with application-service integration
- household-scoped observation and task storage using in-memory and SQLAlchemy repositories
- Alembic migrations for entities, observations, tasks, and media metadata
- household-state reconstruction from persisted observation history
- committed task status updates and storage-level household isolation
- GraphQL household-entity boundary
- authenticated, household-scoped JPEG, PNG, and WebP upload and retrieval over FastAPI
- private filesystem media bytes with PostgreSQL metadata
- Nebius Token Factory MiniCPM vision adapter producing validated, evidence-backed candidates
- household-authorized image-to-observation API persistence, preserving unknown confidence as `null`
- Alembic `0005_unknown_confidence` with PostgreSQL and SQLite-compatible column migration
- condition forecasting
- threshold-crossing prediction
- confidence-aware action policy
- predictive task creation and lifecycle reconciliation
- FastAPI application boundary
- evaluation framework with saved predictions, failure reporting, and an initial five-image kitchen benchmark
- experimental read-only multi-object scene inventory with evidence validation and review flags
- local `.env` loading for FastAPI, Alembic, and standalone vision scripts
- automated backend test suite

Current test baseline:

```text
314 passed
```

Not implemented yet:

- video ingestion and frame sampling; broad, independently validated scene-completeness and calibration benchmarks
- video frame extraction workflow
- Tavily runtime research
- NVIDIA Nemotron calls through Nebius
- end-to-end observation-to-state-to-task processing inside the running API
- production frontend integration
- calendar, email, presence, or quiet-hour context
- durable audit history
- cross-source reactive/predictive task identity unification

## Canonical backend vocabulary

```text
Observation
ConditionType
HouseholdState
ConditionSnapshot
ConditionTrend
Task
TaskUrgency
TaskDecision
TaskDecisionReason
ScoredTask
HouseholdEntity
EntityCandidate
EntityMatchAssessment
EntityResolution
ConditionForecast
ThresholdCrossing
ActionDecision
ActionState
```

The core planning path is:

```text
Observation
    |
    v
ConditionSnapshot
    |
    v
ConditionForecast
    |
    v
ThresholdCrossing
    |
    v
ActionDecision
    |
    v
Task
    |
    v
ScoredTask
```

Reactive work follows a shorter path:

```text
Observation
    |
    v
TaskTrigger
    |
    v
TaskDecision
    |
    v
Task
```

## Repository layout

```text
homhive/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── db/
│   │   ├── media/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/
│   │   └── vision/
│   ├── alembic/
│   ├── alembic.ini
│   ├── tests/
│   └── requirements.txt
├── docs/
│   ├── README.md
│   ├── architecture.md
│   ├── current-state.md
│   ├── decisions.md
│   ├── evaluation.md
│   ├── hackathon.md
│   └── product-spec.md
├── evaluation/
├── frontend/
├── sample-data/
├── LICENSE
└── README.md
```

## Backend setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
pytest
```

The current expected result is:

```text
314 passed
```

To run the FastAPI application from the `backend` directory:

```powershell
uvicorn app.api.app:create_app --factory --reload
```

## Database storage

PostgreSQL persistence uses SQLAlchemy 2.x and Alembic. ORM records and mapping functions remain separate from Pydantic domain models. In-memory repositories provide isolated deterministic tests. Observations and tasks are scoped by household ID at the storage boundary.

From `backend/`, with `DATABASE_URL` pointing to the intended database:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Set `HOMHIVE_ENTITY_STORAGE=sql` to use SQL-backed entity storage through the API; the default is in-memory. Observation and task storage are available through their repositories, but are not yet connected to a top-level ingestion/task API workflow. Database credentials belong in ignored local environment settings.

Image upload, retrieval, and vision observation extraction use opt-in media and vision services. When both `HOMHIVE_MEDIA_ROOT` and `HOMHIVE_HOUSEHOLD_TOKENS` are set, the running API exposes `POST /households/{household_id}/media` and `GET /households/{household_id}/media/{media_id}`. The former setting selects a private filesystem root; the latter is a JSON mapping of household IDs to development bearer tokens. Both must be set together, and the media service needs a valid `DATABASE_URL`. Media files are stored under the configured root, while the `media` PostgreSQL table stores household-scoped metadata. These variables must be configured in the shell that starts Uvicorn; otherwise, the media endpoints are not registered. Token-based household authentication is a development mechanism, not production user authentication. When `NEBIUS_API_KEY` is also configured, the API exposes `POST /households/{household_id}/media/{media_id}/observations` with JSON body `{"location":"kitchen"}`. The request requires the same household bearer token, performs paid external inference, validates candidate observations, and stores accepted observations with `confidence: null`. A response requiring review stores no observations. The vision route is registered only when media configuration and the Nebius key are present. Run from the `backend` directory with `python -m uvicorn app.api.app:app --host 127.0.0.1 --port 8001` or another available port; API documentation is served on that same port.

## Engineering principles

1. Observations describe evidence. Tasks describe work.
2. Raw observations remain separate from derived state.
3. Current state and history serve different purposes.
4. Simple decisions should be deterministic before using an LLM.
5. Task discovery and task ranking are separate concerns.
6. Confidence gates action but uncertain evidence is still preserved.
7. Household identity is separate from observed condition.
8. Forecasts are separate from current state.
9. External providers should sit outside stable internal domain contracts.
10. Stored or public API contracts should not be renamed casually during internal refactors.

## MVP domains

The current product plan uses four representative household domains:

- dishes
- laundry
- plant care
- lawn / outdoor care

These domains exercise different temporal, uncertainty, research, and prioritization behaviors without requiring HomHive to support every household task.

## Planned external integrations

The target architecture includes:

- multimodal vision for structured observations
- FFmpeg for representative video frames
- Tavily for selective external research
- NVIDIA Nemotron through Nebius for cross-domain reasoning
- LangSmith for tracing and evaluation support
- PostgreSQL with SQLAlchemy and Alembic for durable entity, observation, task, and media-metadata storage (implemented); additional orchestration and history capabilities remain planned
- Next.js for the mobile-first PWA

These are target integrations, not all current implementation claims.

## Documentation

Start with [`docs/README.md`](docs/README.md) for the documentation map.

Key files:

- [`docs/architecture.md`](docs/architecture.md) - system structure and data flow
- [`docs/current-state.md`](docs/current-state.md) - what actually exists today
- [`docs/product-spec.md`](docs/product-spec.md) - product scope and MVP behavior
- [`docs/evaluation.md`](docs/evaluation.md) - test and evaluation strategy
- [`docs/decisions.md`](docs/decisions.md) - active architecture decisions
- [`docs/hackathon.md`](docs/hackathon.md) - submission-oriented constraints and integration goals

## License

MIT

## Vision evaluation and experimental scene inventory

Run evaluation tools from `backend` using `python -m evaluation.run_vision` or `python -m evaluation.run_scene`. They operate outside the household database. Human-reviewed evaluation images and reports stay local and must not be committed. The initial five-image kitchen benchmark scored category detection at 5/5, but workload MAE was 0.33. A rubric follow-up completed 4/5 cases, with MAE 0.2025 **among completed cases only**, one unexpected plant-health observation, and a failed case. These are small development results, not generalization claims.

The read-only scene inventory distinguishes detected entities, visible evidence, assessed versus unknown condition, and `rejected_assessments`. The locally reported full suite reached **314 passed**. One completed live scene-inventory call returned only a drain for a kitchen image with multiple visible objects; completeness remains a known limitation. See `docs/scene-inventory.md` and `docs/evaluation.md`.

Local secrets belong in `backend/.env` (not Git). Copy `backend/.env.example`, fill in local values, and avoid printing or committing tokens. Existing process environment variables take precedence.

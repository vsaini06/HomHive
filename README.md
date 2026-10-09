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

The backend currently implements and tests the deterministic foundation needed before external AI integrations are added.

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
- Alembic migrations for entities, observations, and tasks
- household-state reconstruction from persisted observation history
- committed task status updates and storage-level household isolation
- GraphQL household-entity boundary
- condition forecasting
- threshold-crossing prediction
- confidence-aware action policy
- predictive task creation and lifecycle reconciliation
- FastAPI application boundary
- automated backend test suite

Current test baseline:

```text
256 passed
```

Not implemented yet:

- real photo/video perception
- video frame extraction workflow
- Tavily runtime research
- NVIDIA Nemotron calls through Nebius
- observation/task persistence orchestration inside the running API
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
│   │   ├── models/
│   │   ├── repositories/
│   │   └── services/
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
256 passed
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
- PostgreSQL with SQLAlchemy and Alembic for durable entity, observation, and task storage (implemented); additional orchestration and history capabilities remain planned
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

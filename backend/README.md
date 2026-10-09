# HomHive Backend

The HomHive backend is the typed domain and application layer for household state, task discovery, forecasting, entity resolution, and planning.

## Stack

Current backend:

- Python
- FastAPI
- Strawberry GraphQL
- Pydantic
- pytest
- in-memory and SQLAlchemy repository implementations
- PostgreSQL persistence and Alembic migrations for entities, observations, and tasks

Planned:

- Tavily
- NVIDIA Nemotron through Nebius
- LangSmith
- media and vision adapters

## Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Run tests:

```powershell
pytest
```

Expected baseline:

```text
256 passed
```

Run the API from `backend/`:

```powershell
uvicorn app.api.app:create_app --factory --reload
```

## PostgreSQL configuration

From `backend/`, configure `DATABASE_URL` for the intended PostgreSQL database, then run:

```powershell
python -m alembic upgrade head
python -m alembic current
```

`HOMHIVE_ENTITY_STORAGE=sql` selects SQL storage for the household-entity API; omitting the setting retains in-memory storage. The database and local secrets are not committed to Git. Tests should use isolated storage and should not depend on a developer's active SQL environment setting.

## Package structure

```text
backend/app/
├── api/
│   └── graphql/
├── db/
├── models/
├── repositories/
└── services/
```

### Models

Models represent what things are.

Important current models include:

- `Observation`
- `HouseholdState`
- `ConditionSnapshot`
- `ConditionForecast`
- `ThresholdCrossing`
- `ActionDecision`
- `Task`
- `TaskDecision`
- `ScoredTask`
- `HouseholdEntity`
- `EntityCandidate`
- `EntityMatchAssessment`
- `EntityResolution`

### Services

Services represent what the system does.

Current service modules include:

- `condition_tracking.py`
- `reactive_tasks.py`
- `task_ranking.py`
- `entity_resolution.py`
- `household_entity_service.py`
- `state_forecasting.py`
- `action_policy.py`
- `predictive_tasks.py`
- `household_state_reconstruction.py`

### Repositories

Repositories isolate storage behavior.

`HouseholdEntityStorage`, `ObservationStorage`, and `TaskStorage` define storage behavior. In-memory implementations support isolated tests, while SQLAlchemy implementations persist entities, household-scoped observations, and household-scoped tasks. ORM models and mapping functions live under `app/db/`; application services consume Pydantic domain models.

`reconstruct_household_state()` rebuilds `HouseholdState` from household observation history. Task persistence includes current lifecycle status, not a separate audit event log.

## Main deterministic workflows

### Reactive task discovery

```text
Observation
    |
    v
TaskTrigger
    |
    v
decide_task_from_observation()
    |
    v
TaskDecision
    |
    v
task_from_observation()
    |
    v
Task
```

### Condition tracking

```text
Observation history
    |
    v
build_condition_snapshot()
    |
    v
ConditionSnapshot
```

Snapshots use confidence and recency weighting. Trend detection remains deterministic.

### Forecasting

```text
ConditionSnapshot + observations
    |
    v
build_condition_forecast()
    |
    v
ConditionForecast

ConditionSnapshot + observations + threshold
    |
    v
forecast_threshold_crossing()
    |
    v
ThresholdCrossing
```

### Predictive action

```text
ThresholdCrossing
    |
    v
decide_action()
    |
    v
ActionDecision
    |
    v
task_from_action_decision()
    |
    v
sync_predictive_task()
```

### Ranking

```text
Task
    |
    v
score_task()
    |
    v
ScoredTask
    |
    v
rank_tasks()
```

### Entity resolution

```text
EntityCandidate
    |
    v
assess_entity_match()
    |
    v
EntityMatchAssessment
    |
    v
resolve_entity()
    |
    v
EntityResolution
```

## Important boundaries

- `Observation` is evidence, not a task.
- `ConditionSnapshot` is derived current belief, not raw evidence.
- `ConditionForecast` is a projection, not current state.
- `ActionDecision` decides whether forecasted evidence should create work.
- `Task` contains work identity and lifecycle.
- `ScoredTask` adds dynamic planning priority without changing task identity.
- `HouseholdEntity` represents a persistent physical thing independently from observations about it.

## Current limitations

The backend does not yet perform real image understanding, external web research, or model reasoning. Persistent entities are available through configurable API storage. Observation and task persistence are implemented at the repository layer; the application does not yet run a fully integrated persistent ingestion-to-planning pipeline.

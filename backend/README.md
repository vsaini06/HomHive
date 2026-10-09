# HomHive Backend

The HomHive backend is the typed domain and application layer for household state, task discovery, forecasting, entity resolution, and planning.

## Stack

Current backend:

- Python
- FastAPI
- Strawberry GraphQL
- Pydantic
- pytest
- in-memory repository implementations

Planned:

- PostgreSQL / Supabase persistence
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
194 passed
```

Run the API from `backend/`:

```powershell
uvicorn app.api.app:create_app --factory --reload
```

## Package structure

```text
backend/app/
├── api/
│   └── graphql/
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

### Repositories

Repositories isolate storage behavior.

The current household-entity repository is in memory. Durable persistence is still planned.

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

The backend does not yet perform real image understanding, external web research, model reasoning, or durable database persistence.

The in-memory implementation is deliberate while the core contracts and workflows remain under active development.

# HomHive Architecture

## 1. Purpose

HomHive is an intelligence layer that turns household evidence into an evolving plan of work.

The architecture is designed around a simple separation:

```text
Evidence -> State -> Forecast -> Decision -> Work -> Priority
```

External AI providers are adapters around these contracts rather than the contracts themselves.

## 2. Target end-to-end flow

```text
Phone photo / short video
        |
        v
Media validation and frame sampling             [planned]
        |
        v
Vision adapter                                  [planned]
        |
        v
Observation                                     [implemented]
        |
        v
HouseholdState + history                        [implemented]
        |
        v
ConditionSnapshot                               [implemented]
        |
        +--------------------------+
        |                          |
        v                          v
Reactive task discovery       ConditionForecast [implemented]
        |                          |
        |                          v
        |                    ThresholdCrossing   [implemented]
        |                          |
        |                          v
        |                    ActionDecision      [implemented]
        |                          |
        +-------------+------------+
                      |
                      v
                     Task                        [implemented]
                      |
                      v
                  ScoredTask                     [implemented]
                      |
                      v
Selective external research                     [planned]
                      |
                      v
Cross-domain Nemotron planning                  [planned]
                      |
                      v
Mobile plan / executor interface                [planned]
```

## 3. Domain model

### Observation

An `Observation` is one timestamped piece of household evidence.

Important fields include:

- source
- location
- optional entity reference
- condition type
- normalized value
- confidence
- timestamp
- metadata

`ConditionType` is the canonical condition vocabulary.

### HouseholdState

`HouseholdState` keeps both:

- observation history
- current observations

History supports temporal reasoning. Current observations support fast access to the latest evidence.

State identity is owned by `Observation.state_key()`.

Entity identity takes precedence when an `entity_id` exists. Otherwise the key falls back to location plus condition.

### ConditionSnapshot

`ConditionSnapshot` is the system's derived belief about one current condition.

It combines related observations using confidence and recency rather than simply trusting the newest reading.

Current weighting:

```text
recency_weight = 1 / (1 + age_hours)

observation_weight =
    confidence * recency_weight
```

The snapshot also includes a deterministic `ConditionTrend`.

### Task

A `Task` represents work that may need to be performed.

Task identity is separate from the observation that caused it.

Reactive tasks currently use a location/condition-based task key.

Predictive tasks use a predictive key. Unifying reactive and predictive identity is still an open design decision.

### TaskDecision

Reactive task discovery returns a `TaskDecision` so the system can explain why work was or was not created.

Current reasons include:

- task created
- unsupported condition
- below trigger level
- low confidence
- active task already exists

Serialized reason values remain stable where compatibility matters.

### ScoredTask

A `ScoredTask` pairs a `Task` with its current planning score.

Priority is intentionally not stored as permanent task identity.

### HouseholdEntity

`HouseholdEntity` represents a persistent physical household object or area.

Examples:

- plant
- appliance
- fixture
- area

Entity identity is separate from observations about changing condition.

### EntityCandidate

An `EntityCandidate` is a temporary identification result. It is not automatically persisted as a household entity.

### EntityMatchAssessment

`EntityMatchAssessment` records evidence about whether a candidate may refer to an existing physical entity.

### EntityResolution

`EntityResolution` represents the resolution outcome.

The entity workflow preserves uncertainty instead of forcing every candidate into an existing/new binary.

### ConditionForecast

`ConditionForecast` projects one condition forward.

Forecast confidence is distinct from snapshot confidence.

### ThresholdCrossing

`ThresholdCrossing` represents a forecast that a condition is expected to reach a configured level.

A forecast and a threshold crossing are separate concepts.

### ActionDecision

`ActionDecision` converts a forecasted threshold event into one of the current action states:

- `NONE`
- `MONITOR`
- `PLAN`
- `ACT_NOW`

Low-confidence predictions may remain visible without creating household work.

## 4. Application services

### Condition tracking

`condition_tracking.py`

Responsibilities:

- recency weighting
- observation weighting
- trend detection
- condition snapshot creation
- household snapshot grouping

### Reactive tasks

`reactive_tasks.py`

Responsibilities:

- deterministic task triggers
- confidence gates
- duplicate active-task prevention
- explainable task decisions

Current configured reactive domains include dishes and laundry.

### Task ranking

`task_ranking.py`

Current score:

```text
priority =
    urgency_score * 0.60
    + confidence * 0.30
    + effort_score * 0.10
```

Shorter effort receives a small advantage, but urgency remains dominant.

### State forecasting

`state_forecasting.py`

Responsibilities:

- estimate hourly change
- project condition level
- estimate forecast confidence
- build forecasts
- estimate time to threshold
- create threshold-crossing predictions

### Action policy

`action_policy.py`

Responsibilities:

- convert threshold crossings into action states
- prevent weak forecasts from automatically creating work
- distinguish monitoring, planning, and immediate action

### Predictive tasks

`predictive_tasks.py`

Responsibilities:

- create tasks from actionable forecast decisions
- preserve predictive task lifecycle
- dismiss no-longer-actionable predictive tasks
- reactivate dismissed predictive work when it becomes actionable again

### Entity resolution

`entity_resolution.py`

Responsibilities:

- filter incompatible entities
- assess available match evidence
- resolve candidate identity conservatively

### Household entity service

`household_entity_service.py`

Application layer between the API boundary and repository.

## 5. Repository layer

The current entity repository is in memory.

This is a development-stage boundary, not the final storage architecture.

Planned persistence:

```text
PostgreSQL / Supabase
```

The storage layer should eventually preserve:

- observations
- derived state
- entities
- tasks
- task lifecycle
- forecasts
- decisions
- external evidence
- trace metadata

## 6. API boundary

HomHive currently uses FastAPI and Strawberry GraphQL.

The GraphQL entity boundary uses Python-facing names that describe the domain cleanly while preserving deliberate public schema names where compatibility matters.

The API should remain thin:

```text
Request
  |
  v
Query / Mutation
  |
  v
Application Service
  |
  v
Repository / Domain Service
  |
  v
Domain Model
  |
  v
GraphQL view mapping
```

## 7. Planned AI and research adapters

### Vision

Planned behavior:

```text
media
  |
  v
vision model
  |
  v
structured observations / entity clues
```

Vision should produce structured evidence. It should not decide the final household plan.

### Tavily

Tavily should be called conditionally when internal household state is not enough.

Likely use cases:

- unfamiliar plants
- appliance/model research
- maintenance guidance
- external or seasonal lawn context
- unfamiliar household situations

Routine dish and laundry task discovery should not require a web search.

### Nemotron through Nebius

Nemotron is planned as the cross-domain reasoning layer.

It should reason over structured facts, forecasts, constraints, and selected evidence rather than inventing household state from prose.

## 8. Major invariants

1. Observation is not state.
2. State is not forecast.
3. Forecast is not action.
4. Action is not task identity.
5. Task identity is not priority.
6. Entity identity is not condition.
7. Missing evidence is not contradictory evidence.
8. Low confidence can block action without deleting evidence.
9. External providers should not leak into core models.
10. Durable persistence is not claimed until it exists.

## 9. Open architecture work

- reactive/predictive task identity unification
- durable persistence
- media ingestion contract
- vision adapter
- external evidence model and cache
- research routing
- cross-domain planning contract
- user-context model
- executor capability model
- top-level orchestration service

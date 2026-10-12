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
Phone image (JPEG / PNG / WebP)       Short video
            |                            |
            v                            v
Image authentication, validation,      Video ingestion and
and private storage [implemented]      frame sampling [planned]
            |                            |
            +-------------+--------------+
                          |
                          v
Vision adapter                                  [implemented for images]
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

## Persistence boundaries

```text
PostgreSQL
  -> SQLAlchemy ORM records
  -> explicit record/domain mapping
  -> repository contracts
  -> Pydantic domain models and application services
```

Entity, observation, task, and media-metadata tables are managed through Alembic. Observation and task repositories accept `household_id` at the storage boundary, without requiring household ownership fields in the corresponding domain models. Historical observations can be replayed through `reconstruct_household_state()` to restore `HouseholdState`. Derived snapshots and forecasts are recomputed, not stored as authoritative records.

The entity API can use SQL storage through `HOMHIVE_ENTITY_STORAGE=sql`. Observation-to-task persistence has been verified with the repositories in independent Python processes, but is not wired into an automatic API orchestration workflow. Task status is stored; transition-by-transition audit history is not implemented.

Media uses a separate persistence boundary: image bytes live in a configurable private filesystem root, while the `media` table stores a composite `(household_id, id)` key with content type, byte size, and creation time. `MediaService` coordinates the file and metadata write and removes the file if the metadata transaction fails. Stored media does not automatically become a domain `Observation`.

## Media HTTP boundary

The optional media router exposes:

```text
POST /households/{household_id}/media
  -> HTTP bearer authorization
  -> size, MIME, and file-signature validation
  -> MediaService.save_image()
  -> LocalMediaStorage + PostgreSQL MediaRecord

GET /households/{household_id}/media/{media_id}
  -> HTTP bearer authorization
  -> household-scoped MediaRecord lookup
  -> LocalMediaStorage.read()
  -> image bytes, Cache-Control: private, no-store
```

The router is registered only when `HOMHIVE_MEDIA_ROOT` and `HOMHIVE_HOUSEHOLD_TOKENS` are both configured. Either missing setting while the other is present causes startup to fail; when both are absent, media routes are disabled. A valid `DATABASE_URL` is required for SQL-backed media metadata. Household tokens are a temporary development mechanism rather than a complete user identity and membership model. Missing or mismatched tokens return `403`; a media record not present under the authorized household returns `404`.

The implementation accepts JPEG, PNG, and WebP images up to 10 MiB. Authenticated stored images can be analyzed by a Nebius MiniCPM vision adapter. The extraction service validates directly visible candidates, attaches visual evidence and media provenance, then persists accepted observations under the authorized household. Video ingestion and frame sampling remain unimplemented.

## 3. Domain model

### Observation

An `Observation` is one timestamped piece of household evidence.

Important fields include:

- source
- location
- optional entity reference
- condition type
- normalized value
- confidence (`float` in `[0, 1]` or `None` when unknown)
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
    confidence * recency_weight  # only when confidence is known
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

The repository layer offers in-memory and SQLAlchemy implementations behind explicit storage contracts.

Persisted PostgreSQL data includes:

- household entities
- household-scoped raw observations and their timestamps/metadata
- household-scoped tasks and their current lifecycle status
- household-scoped media metadata (image bytes are stored separately)

Household state is reconstructed from ordered observation history, rather than persisted as an independent authoritative snapshot. Full status-change audit events, derived forecasts, decisions, external evidence, and traces are not yet persisted.

## 6. API boundary

HomHive currently uses FastAPI and Strawberry GraphQL, with HTTP REST endpoints for media transfer.

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
10. Durable storage and complete audit history are different capabilities.
11. Household media access is enforced at the HTTP boundary and data lookup.
12. Media bytes and domain observations are separate resources.

## 9. Open architecture work

- reactive/predictive task identity unification
- persistent workflow orchestration and full audit history
- video ingestion and frame sampling
- vision benchmark and workload calibration
- external evidence model and cache
- research routing
- cross-domain planning contract
- user-context model
- executor capability model
- top-level orchestration service

## Implemented image-to-observation path

```text
Authenticated stored image (household-scoped media lookup)
  -> Nebius Token Factory MiniCPM vision provider
  -> structured candidate with category, value, location, visible evidence
  -> conservative validation / review decision
  -> Observation(source=photo, confidence=None, metadata={media_id, visible_evidence})
  -> household-scoped ObservationStorage / PostgreSQL
```

The endpoint is `POST /households/{household_id}/media/{media_id}/observations` and requires the household bearer token and a JSON location. Inference is opt-in and uses the external `NEBIUS_API_KEY`; credentials and local media bytes are not committed. Absent or unassessable domains must not be represented as zero-valued observations. A review-needed extraction does not create observations. Unknown confidence remains `NULL` in persistence; reactive task triggers do not treat unknown confidence as passing a confidence threshold, and confidence-weighted derived computations must handle it explicitly. The endpoint persists observations only: it does not automatically create tasks or complete a planning pipeline.

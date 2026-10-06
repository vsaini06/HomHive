# HomHive Current State

Last updated: October 2026

## Current Milestone

Day 10 of the 38-day HomHive build roadmap.

Current focus: deterministic forecasting, threshold prediction, intervention decisions, and predictive task lifecycle.

Current automated test result:

```text
194 passed
```

## What Exists Today

HomHive currently has a tested Python backend foundation covering:

- observation modeling
- household state history
- deterministic task discovery
- confidence-aware task discovery
- explainable discovery results
- task deduplication
- deterministic task prioritization
- temporal state aggregation
- trend detection
- household entity modeling
- entity-aware state identity
- entity identification contracts
- deterministic entity resolution
- FastAPI application foundation
- Strawberry GraphQL API
- repository/service separation
- deterministic state forecasting
- threshold-crossing prediction
- forecast confidence
- intervention decisions
- predictive task discovery
- predictive task reconciliation
- predictive task lifecycle

The project does not yet process real household images or call external AI/research services.

---

## Day 1: Repository Foundation

Created the initial HomHive repository and project structure.

Added:

- backend
- frontend
- sample data
- evaluation structure
- documentation
- README
- MIT license
- `.gitignore`

Initial documentation included:

- `architecture.md`
- `evaluation.md`
- `hackathon.md`
- `product-spec.md`

---

## Day 2: Core Domain Models

Created the Python backend model layer.

### Observation

Implemented `Observation` with:

- id
- source
- location
- category
- value
- confidence
- timestamp
- metadata

Observation value and confidence are validated between `0.0` and `1.0`.

Supported observation sources include:

- photo
- video
- user input
- history
- external research

Initial categories include:

- dish load
- laundry load
- plant condition
- lawn condition
- maintenance status

### HouseholdState

Implemented:

```text
observation_history
current_observations
```

Historical observations remain available after current state changes.

### Task

Implemented the initial `Task` model with:

- id
- task key
- description
- source observation
- urgency
- effort
- deadline
- confidence
- status
- creation time
- metadata

---

## Day 3: Deterministic Task Discovery

Created the service layer and deterministic task-discovery rules.

Initial rules cover dish and laundry conditions.

Task discovery separates:

```text
Observation
```

from:

```text
Task
```

Added stable `task_key` values for duplicate detection.

Active pending or in-progress tasks prevent duplicate work from being created.

Completed or dismissed work can later be generated again if the condition returns.

Observation history remains independent from task deduplication.

End-of-day result:

```text
21 tests passing
```

---

## Day 4: Confidence and Explainability

Extended task discovery with category-specific confidence requirements.

Current task creation requires both:

- condition threshold satisfied
- minimum confidence satisfied

Low-confidence observations remain in household history even when they do not create tasks.

Repeated uncertain observations do not automatically increase confidence.

Added:

```text
TaskDiscoveryResult
TaskDiscoveryReason
```

Detailed discovery can explain outcomes including:

- task created
- unsupported category
- below threshold
- low confidence
- duplicate active task

The original `Task | None` discovery interface remains available.

---

## Day 5: Task Prioritization

Separated task prioritization from task discovery.

Current priority signals:

```text
urgency       60%
confidence    30%
effort        10%
```

Effort score:

```text
1 / (1 + effort_minutes / 30)
```

Equal priority scores use task ID as a deterministic fallback.

These values are MVP heuristics.

---

## Day 6: Temporal State Aggregation

Added `AggregatedState`.

Raw observations remain preserved while aggregation produces a derived current belief.

Observation weighting:

```text
confidence * recency_weight
```

Recency:

```text
1 / (1 + age_hours)
```

Current value is calculated using a weighted average.

Aggregated confidence currently uses the maximum contributing observation confidence.

Repeated observations do not automatically increase confidence.

### Trend Detection

Added:

- rising
- stable
- falling
- unknown

The current stability threshold is:

```text
0.05
```

Timestamp ordering is used before trend calculation.

Floating-point changes are normalized before boundary comparison.

---

## Day 7: Household Entities

Added persistent household entity representation.

Implemented:

- `EntityType`
- `HouseholdEntity`
- optional specific identity
- identification confidence
- extensible attributes
- optional `Observation.entity_id`

State identity was updated.

When an entity is known:

```text
entity_id:category
```

When an entity is not known:

```text
location:category
```

`Observation.state_key()` is the canonical state-key policy.

This prevents multiple entities of the same category in the same location from being merged.

End-of-day result:

```text
77 tests passing
```

---

## Day 8: Entity Identification and Resolution

Implemented:

- `EntityIdentificationCandidate`
- `EntityResolutionStatus`
- `EntityResolutionResult`
- `EntityMatchEvidence`
- compatibility filtering
- match-evidence generation
- evidence-aware resolution
- automatic resolution orchestration

Resolution outcomes:

```text
MATCH
CREATE
UNCERTAIN
```

Identification and resolution remain separate.

Identification asks:

```text
What does this object appear to be?
```

Resolution asks:

```text
Does this correspond to an existing physical household entity?
```

Current compatibility considers:

- entity type
- observed location
- known identity conflicts

Current evidence considers:

- exact identity agreement
- shared attribute agreement
- conflicting attributes

Automatic matching currently uses:

```text
MATCH_THRESHOLD = 0.80
```

This is an MVP heuristic.

Explicit contradictions prevent automatic strong matching.

No real vision model is connected yet.

End-of-day result:

```text
113 tests passing
```

---

## Day 9: FastAPI and GraphQL Foundation

Added the initial application/API layer.

Technologies:

```text
FastAPI
Strawberry GraphQL
```

Current API strategy is hybrid.

REST currently provides:

```text
GET /health
```

GraphQL provides entity operations.

Implemented GraphQL behavior includes:

- retrieve entity by ID
- retrieve collections of entities
- filter entity queries
- rename an entity

Added separation between:

```text
GraphQL Resolver
      ↓
Entity Service
      ↓
Entity Repository
      ↓
Domain Model
```

Business validation remains in the service/domain path rather than being embedded entirely in GraphQL.

### Application Factory

Introduced application construction through `create_app()`.

Application dependencies are created at the application boundary and provided to GraphQL through context.

### Repository

Entity storage currently uses an in-memory repository.

Persistence has not yet been implemented.

### Test Isolation

Each test can create a separate FastAPI application instance.

State is shared within one application instance but isolated between different application instances.

End-of-day result:

```text
141 tests passing
```

---

## Day 10: Forecasting and Predictive Intervention

Day 10 introduced the first proactive state-prediction path.

### StateForecast

Added `StateForecast`.

A forecast contains:

- location
- category
- current value
- predicted value
- rate per hour
- forecast horizon
- predicted timestamp
- trend
- confidence

### Rate of Change

Implemented deterministic rate calculation using timestamped observations.

```text
(newest_value - oldest_value)
/
elapsed_hours
```

Fewer than two observations produce a zero rate.

Non-positive elapsed time also produces a zero rate.

### Future Value Prediction

Implemented linear future-state projection.

```text
current_value
+ rate_per_hour * forecast_hours
```

Values are clamped between `0.0` and `1.0`.

Forecast horizons must be positive.

This is a deterministic MVP baseline, not a learned forecasting model.

---

## Forecast Confidence

Forecast confidence is calculated separately from aggregated-state confidence.

Current heuristic considers:

- average observation confidence
- number of observations
- forecast distance

Evidence factor:

```text
min(1.0, observation_count / 5.0)
```

Distance factor:

```text
1 / (1 + forecast_hours / 24.0)
```

Longer forecasts therefore receive lower confidence.

---

## Threshold Prediction

Added `ThresholdPrediction`.

HomHive can estimate how long a rising state may take to cross a configured threshold.

If:

```text
current_value >= threshold
```

then:

```text
hours_to_threshold = 0
```

If the state is not moving toward the threshold, no crossing is predicted.

Threshold prediction also includes a predicted crossing timestamp and confidence.

---

## Intervention Decisions

Added:

```text
InterventionDecision
InterventionStatus
```

Current statuses:

```text
NONE
MONITOR
PLAN
ACT_NOW
```

The decision layer is separate from forecasting.

A forecast describes expected future state.

An intervention decision determines whether that prediction currently justifies action.

Current behavior considers:

- forecast confidence
- time to threshold
- planning window

Low-confidence predictions remain in monitoring.

Conditions already at their threshold can produce `ACT_NOW`.

---

## Predictive Task Discovery

Added predictive task generation from actionable intervention decisions.

Current mapping:

```text
PLAN
    ↓
MEDIUM urgency task

ACT_NOW
    ↓
HIGH urgency task

MONITOR / NONE
    ↓
No new task
```

Predictive tasks do not require a single source observation.

`Task.source_observation_id` is therefore now optional.

This avoids creating fake observation provenance for tasks derived from multiple historical observations and a forecast.

---

## Predictive Task Identity

Predictive tasks use deterministic task identity based on the affected state.

Repeated evaluations of the same predictive condition retain the same task identity even when:

- confidence changes
- time to threshold changes
- intervention status changes

This provides the basis for task reconciliation.

---

## Predictive Task Reconciliation

Added reconciliation for repeated predictive evaluations.

When no matching predictive task exists:

```text
create task
```

When the same task already exists:

```text
update existing task
```

The existing task object is preserved while changing information such as:

- urgency
- confidence
- metadata
- intervention status

Unrelated tasks are not modified.

---

## Predictive Task Lifecycle

Predictive tasks now respond to changing conditions.

Current lifecycle:

```text
PLAN
    ↓
Create task

ACT_NOW
    ↓
Escalate existing task

MONITOR
    ↓
Dismiss existing predictive task

PLAN / ACT_NOW later
    ↓
Reactivate existing logical task
```

Predictive tasks are dismissed rather than deleted when a condition no longer requires action.

This preserves a path for future historical evaluation.

Persistent lifecycle history is not available yet because the database layer has not been implemented.

---

## Current Architecture

The implemented intelligence flow is now approximately:

```text
Observations
     ↓
HouseholdState
     ↓
State Aggregation
     ↓
AggregatedState
     ↓
Forecasting
     ↓
Threshold Prediction
     ↓
Intervention Decision
     ↓
Predictive Task Discovery
     ↓
Task Reconciliation
     ↓
Tasks
     ↓
Prioritization
```

A parallel observation-driven task-discovery path still exists for immediately actionable deterministic conditions.

Not every layer is yet connected through one top-level orchestration service.

---

## Current Test Status

At the end of Day 10:

```text
194 automated tests passing
```

The current suite covers the major implemented domain and service behaviors.

The test count is used as a development checkpoint and should not be interpreted as production-readiness coverage.

---

## External Services Available

The project currently has access to:

- Nebius
- Tavily
- LangSmith
- Toloka
- Tandem

None of these services are currently integrated into the implemented core pipeline.

Planned roles include:

- Nebius for model inference and reasoning
- Tavily for conditional external research
- LangSmith for tracing and evaluation
- Toloka for potential human evaluation/data validation
- Tandem after its useful role is confirmed

---

## Not Implemented Yet

Major remaining components include:

- real photo ingestion
- video ingestion
- vision-model integration
- automatic visual entity identification
- Tavily research
- Nebius/Nemotron reasoning
- LangSmith tracing
- persistent database storage
- frontend integration
- calendar context
- email context
- quiet hours
- presence and availability reasoning
- execution-window planning
- learned forecasting
- full predictive/reactive task reconciliation

These should not be treated as existing capabilities until implemented and tested.
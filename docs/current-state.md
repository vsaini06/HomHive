# HomHive Current State

Last updated: October 8, 2026

## Status

The deterministic backend foundation is stable after the naming and architecture refactor.

Current test baseline:

```text
194 passed
```

The current codebase has clean canonical naming and no targeted legacy aliases from the completed refactor.

## Implemented

### Core evidence and state

- `Observation`
- `ObservationSource`
- `ConditionType`
- `HouseholdState`
- optional observation-to-entity references
- observation history
- current observation tracking
- stable state-key policy

### Condition tracking

- `ConditionSnapshot`
- `ConditionTrend`
- confidence and recency weighting
- deterministic trend detection
- grouped household condition snapshots

### Reactive task discovery

- `TaskTrigger`
- `TaskDecision`
- `TaskDecisionReason`
- dish-load trigger
- laundry-load trigger
- confidence gates
- duplicate active-task prevention
- task traceability to source observations

### Task lifecycle and ranking

- `Task`
- `TaskStatus`
- `TaskUrgency`
- `ScoredTask`
- deterministic scoring
- deterministic tie ordering

### Household entities

- `HouseholdEntity`
- `EntityCandidate`
- `EntityMatchAssessment`
- `EntityResolution`
- deterministic compatibility checks
- deterministic match assessment
- conservative entity resolution
- in-memory household-entity repository
- household-entity application service

### API

- FastAPI application boundary
- Strawberry GraphQL household-entity boundary
- service/repository separation
- explicit domain-to-GraphQL mapping

### Forecasting

- `ConditionForecast`
- hourly-change estimation
- condition projection
- forecast-confidence estimation
- time-to-threshold estimation
- `ThresholdCrossing`

### Predictive action

- `ActionState`
- `ActionDecision`
- confidence-aware action policy
- predictive task creation
- predictive task update/reuse
- dismissal when no longer actionable
- reactivation when actionable again

## Canonical workflows

### Reactive

```text
Observation
  -> TaskTrigger
  -> TaskDecision
  -> Task
```

### State and forecast

```text
Observation history
  -> ConditionSnapshot
  -> ConditionForecast
  -> ThresholdCrossing
```

### Predictive work

```text
ThresholdCrossing
  -> ActionDecision
  -> Task
```

### Ranking

```text
Task
  -> ScoredTask
  -> ranked task list
```

### Entity resolution

```text
EntityCandidate
  -> EntityMatchAssessment
  -> EntityResolution
  -> HouseholdEntity
```

## Current storage

The current repository implementation is in memory.

Do not describe HomHive as having durable persistence yet.

## Not implemented yet

- real image analysis
- real video analysis
- FFmpeg frame extraction
- Tavily runtime calls
- Nemotron runtime calls
- Nebius runtime integration
- LangSmith tracing
- PostgreSQL / Supabase persistence
- production Next.js workflow
- calendar/email integration
- user availability or presence
- quiet hours
- execution-window planning
- durable audit history
- external evidence cache
- full cross-domain reasoning
- top-level end-to-end orchestration
- unified task identity across reactive and predictive sources

## Next engineering milestone

The refactor is complete. The next feature work should return to the execution roadmap rather than continuing to rename stable domain concepts.

Recommended next sequence:

1. reconcile the roadmap after forecasting displaced the original persistence day
2. add durable persistence or media ingestion as the next concrete platform capability
3. preserve the 194-test baseline during that work
4. integrate external services only behind stable adapters

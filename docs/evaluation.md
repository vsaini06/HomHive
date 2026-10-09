# HomHive Evaluation

## Purpose

HomHive should be evaluated as a decision system, not only as a collection of API endpoints.

The evaluation strategy is split into:

1. deterministic unit and flow tests
2. scenario-based system evaluation
3. external research evaluation
4. model-planning evaluation
5. end-to-end product evaluation

## Current automated baseline

The current backend suite passes:

```text
256 tests
```

These tests currently cover the deterministic foundation, including:

- observation validation
- household state behavior
- condition tracking
- trend detection
- reactive task discovery
- duplicate prevention
- task ranking
- entity models
- entity matching and resolution
- repository/service behavior
- GraphQL mapping and API behavior
- condition forecasting
- threshold crossing
- action policy
- predictive task lifecycle
- SQLAlchemy and in-memory repository contracts for entities, observations, and tasks
- database transaction and lifecycle behavior
- household-scoped storage isolation
- reconstruction of household state from persisted observation history
- persistence and GraphQL storage-configuration behavior

This number is a regression baseline, not a claim of product-level accuracy.

## Deterministic evaluation principles

### Exact behavior

Rules should have tests for:

- normal cases
- threshold boundaries
- invalid inputs
- low confidence
- duplicate work
- lifecycle changes
- deterministic ordering

### Separation tests

Tests should protect architecture boundaries such as:

- observation vs task
- raw evidence vs derived state
- forecast vs current state
- entity identity vs observed condition
- task identity vs priority

## Persistence evaluation

Storage tests verify committed reads and updates across independent sessions, chronological household histories, metadata round trips, and duplicate IDs. Live PostgreSQL checks have also exercised state reconstruction and sequential prevention of duplicate active tasks across independent processes. These checks do not establish atomicity or concurrent duplicate protection for the entire processing pipeline, and the system does not yet maintain full task-transition audit events.

## Planned golden scenarios

A future golden scenario set should cover complete household situations rather than isolated functions.

Suggested scenario categories:

### Dishes

- low load, no task
- high confident load, create reactive task
- repeated scan, do not duplicate active work
- rising load, forecast near threshold
- task completed, later condition can create work again

### Laundry

- moderate load, monitor
- rising load, plan ahead
- already above threshold, act now
- user unavailable, defer in later planning layer

### Plant

- uncertain condition
- unknown species
- candidate identity requires verification
- Tavily research materially changes guidance
- conflicting entity evidence stays uncertain

### Lawn / outdoor

- slowly changing condition
- longer threshold horizon
- external seasonal context affects plan

## Forecast evaluation

Forecast tests should measure separately:

- direction accuracy
- projected value error
- time-to-threshold error
- confidence calibration

The current implementation is deterministic and intentionally simple. Future learned or model-based forecasting should be compared against this baseline rather than replacing it without evidence.

## Research evaluation

When Tavily is integrated, evaluate:

- whether a search was actually necessary
- query relevance
- source quality
- evidence freshness
- duplicate search avoidance
- whether the returned evidence changed the decision appropriately

A good research router should receive credit for correctly *not* searching routine situations.

## Reasoning evaluation

When Nemotron is integrated, evaluate:

- schema-valid output rate
- ranking consistency
- constraint adherence
- evidence use
- unsupported-claim rate
- fallback behavior
- latency
- token usage
- stability across repeated runs

The model should be compared against the deterministic ranking baseline.

## End-to-end evaluation

The final product should be tested from user input to visible action plan.

A judge-ready scenario should record:

```text
input media
-> extracted observations
-> state update
-> discovered / forecast tasks
-> research decision
-> external evidence, if any
-> final plan
-> explanation
```

## Evaluation integrity

Do not publish fabricated accuracy, latency, cost, or reliability metrics.

Only report a metric after:

- the evaluation set exists
- the procedure is reproducible
- the result has actually been measured

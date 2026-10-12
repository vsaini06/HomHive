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
282 tests
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
- image MIME/signature and size validation
- HTTP bearer authorization and household-scoped media lookup
- persisted media retrieval across new service instances and cleanup on failed metadata transactions
- OpenAPI bearer security declarations
- unknown-confidence domain and decision guards
- validated vision-candidate handling and persistence service behavior
- SQLite-compatible observation-nullability migration

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

## Media evaluation

Media tests exercise accepted image types, rejection of mismatched file signatures and oversize uploads, authorization failures, household-scoped lookups, persistent retrieval, and file cleanup if metadata persistence fails. The service returns image bytes with a private no-store cache directive.

A live HTTP retrieval of an uploaded JPEG was compared to its original file using SHA-256 and matched. Separate valid household tokens were used to verify that a media record saved under one household was not returned from another household's lookup (`404`), and that tokens could not authorize requests against the other household's path (`403`). These checks provide evidence for the tested local environment, not a complete production security assessment.

## Vision inference and persistence verification

A live Nebius MiniCPM check on a clean-sink image produced a single `dish_load = 0.0` candidate with visible evidence and omitted unrelated laundry, plant, and lawn conditions. A cluttered-sink image produced `dish_load = 1.0` with supporting visual evidence; that numeric output is not yet calibrated against a gold standard. The backend accepted and stored a clean-sink observation with `confidence = NULL`. An independent PostgreSQL query returned the persisted row, confirming storage beyond the HTTP response. The authorized endpoint was visible in the OpenAPI/Swagger UI of the freshly started server.

These checks verify a narrow working integration, not general vision reliability. A reproducible image evaluation set should cover empty, light, moderate, and heavy workloads; absent conditions versus true zero; mixed scenes; ambiguous framing; visual evidence quality; review-needed behavior; repeatability; provider errors; and invalid or unsupported outputs. Report category precision/recall, value error under a defined workload rubric, false-positive omissions, and human-review rates only after executing that evaluation.

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

## Day 15 vision measurements (development set)

The initial five-image kitchen test used provisional human `dish_load` labels `0.0`, `0.2`, `0.45`, `0.7`, `1.0`. MiniCPM predicted `0.0` for the clean sink and `1.0` for every nonempty sink: five category true positives, no false positives or negatives, matched severity MAE **0.33**, and **40%** within configured tolerance.

The revised prompt completed four of five evaluations (80% completion) and yielded matched-only severity MAE **0.2025** and tolerance agreement **50%** among completed cases. It also produced one unexpected `plant_condition`, gave the clean sink a nonzero workload, and failed on the heavy case. Never present 0.2025 as directly comparable to the five-case 0.33 baseline without qualifying selection bias. Local evaluation reports and images may reveal household details and should remain ignored by Git.

An experimental scene-inventory run successfully produced valid output but listed only a drain in a visibly multi-object kitchen. The measurable next target is scene *completeness*, with a human-annotated set of expected visible entities, label normalization rules, object recall and false-detection counts, and separate unsupported-condition rates. Structural tests (314 locally passed across the backend) are not model-quality metrics. Scene analysis does not write to PostgreSQL.

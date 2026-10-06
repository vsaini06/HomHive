---

## ADR-046: FastAPI and GraphQL Use a Hybrid API Strategy

### Status

Accepted

### Decision

HomHive uses FastAPI as the application host and Strawberry GraphQL for structured application queries and mutations.

REST remains available for endpoints that do not benefit from GraphQL, including the current health endpoint.

### Reason

Not every application operation needs the same interface.

GraphQL is useful for querying connected household data and exposing application operations with explicit schemas.

REST remains simpler for operational endpoints and future upload-oriented workflows.

The project therefore does not require all backend functionality to be forced through GraphQL.

---

## ADR-047: GraphQL Resolvers Do Not Own Application State

### Status

Accepted

### Decision

GraphQL resolvers receive application dependencies through the GraphQL context.

Repositories and services are constructed at the application boundary rather than inside individual resolvers.

### Reason

Resolvers should translate API requests into application operations rather than manage storage or dependency lifecycles themselves.

This also allows tests to construct isolated application instances with independent state.

---

## ADR-048: Repository Access Is Separated from GraphQL and Domain Models

### Status

Accepted

### Decision

Entity storage is accessed through a repository boundary.

The current implementation uses an in-memory repository.

### Reason

API behavior should not depend directly on the eventual persistence technology.

The repository boundary allows the current in-memory implementation to be replaced later without moving storage logic into GraphQL resolvers or domain models.

---

## ADR-049: Application Instances Own Their Current In-Memory State

### Status

Accepted for current implementation

### Decision

Repository and service instances are created for each FastAPI application instance.

Tests create independent application instances.

### Reason

Module-level mutable state can leak data between tests and make application behavior depend on import history.

Application-scoped state provides deterministic test isolation while persistence is still in memory.

This decision can be revisited when persistent storage is introduced.

---

## ADR-050: Forecasting Is Separate from Aggregated State

### Status

Accepted

### Decision

`AggregatedState` represents the current derived belief about a household condition.

`StateForecast` represents a prediction about a possible future value.

These remain separate models.

### Reason

Current state and predicted state have different semantics and confidence characteristics.

Combining them would make it difficult to distinguish observed or derived household conditions from projections.

---

## ADR-051: Initial Forecasting Uses a Deterministic Baseline

### Status

Accepted for MVP

### Decision

The initial forecasting implementation uses timestamped rate of change and linear projection rather than a learned forecasting model.

Current rate:

```text
(newest_value - oldest_value)
/
elapsed_hours
```

Current projection:

```text
current_value
+ rate_per_hour * forecast_hours
```

Predicted values are clamped to the valid normalized state range.

### Reason

The project needs a predictable and testable forecasting baseline before introducing learned models.

A deterministic baseline also provides something future forecasting approaches can be evaluated against.

---

## ADR-052: Forecast Confidence Is Separate from State Confidence

### Status

Accepted

### Decision

Forecast confidence is calculated independently from `AggregatedState.confidence`.

The current forecast-confidence heuristic considers:

- observation confidence
- evidence count
- forecast horizon

### Reason

Confidence in the current state does not imply equal confidence in a future prediction.

Prediction uncertainty generally increases with forecast distance and depends on the amount of historical evidence available.

---

## ADR-053: Forecast Confidence Uses a Transparent MVP Heuristic

### Status

Accepted for MVP

### Decision

The current forecast-confidence calculation uses:

```text
average_observation_confidence
*
evidence_factor
*
distance_factor
```

where:

```text
evidence_factor =
min(1.0, observation_count / 5.0)
```

and:

```text
distance_factor =
1 / (1 + forecast_hours / 24.0)
```

### Reason

The current implementation needs deterministic confidence behavior that can be tested and inspected.

The formula is not considered statistically calibrated and should be evaluated against realistic data before being treated as a reliable probability estimate.

---

## ADR-054: Threshold Prediction Is Separate from General Forecasting

### Status

Accepted

### Decision

`ThresholdPrediction` represents an estimated crossing of a configured condition threshold.

A general state forecast does not automatically imply a threshold event.

### Reason

The system needs to distinguish:

```text
What value might this state reach?
```

from:

```text
When might this condition become actionable?
```

Keeping threshold prediction explicit also allows intervention policy to operate on a clear event representation.

---

## ADR-055: No Threshold Prediction Is Created When a Crossing Is Not Expected

### Status

Accepted

### Decision

When the current rate does not indicate movement toward an unmet threshold, threshold prediction returns no crossing prediction.

If the threshold has already been reached:

```text
hours_to_threshold = 0
```

### Reason

An artificial crossing time should not be created when the available trend does not support one.

The already-reached case remains meaningful because it can immediately influence intervention policy.

---

## ADR-056: Prediction and Intervention Are Separate Layers

### Status

Accepted

### Decision

Forecasting and threshold prediction describe expected future state.

`InterventionDecision` determines whether the prediction currently warrants monitoring, planning, or immediate action.

### Reason

A prediction should not automatically create a task.

Separating prediction from intervention allows the system to account for confidence and planning horizon before turning predicted conditions into work.

---

## ADR-057: Intervention Uses Explicit Decision States

### Status

Accepted

### Decision

The current intervention states are:

```text
NONE
MONITOR
PLAN
ACT_NOW
```

### Reason

A binary act/do-not-act decision does not represent the intermediate states needed for predictive planning.

In particular, `MONITOR` allows HomHive to retain awareness of a forecast without prematurely creating work.

---

## ADR-058: Low-Confidence Predictions Do Not Automatically Create Tasks

### Status

Accepted

### Decision

Predictions below the configured minimum intervention confidence remain in `MONITOR`.

### Reason

Predictive task creation should require stronger evidence than simply having a projected threshold crossing.

This reduces unnecessary tasks caused by weak or long-range forecasts.

---

## ADR-059: Predictive Tasks May Have No Single Source Observation

### Status

Accepted

### Decision

`Task.source_observation_id` is optional.

Observation-driven tasks may reference the observation that created them.

Prediction-driven tasks may use:

```text
source_observation_id = None
```

### Reason

A predictive task can be derived from multiple observations, aggregated state, a forecast, and an intervention decision.

Assigning one arbitrary observation as the source would create misleading provenance.

HomHive should not invent provenance to satisfy a schema requirement.

---

## ADR-060: Predictive Task Identity Is Stable Across Forecast Changes

### Status

Accepted

### Decision

Changes to:

- forecast confidence
- hours to threshold
- intervention status

do not by themselves create a different predictive task identity.

The predictive task key is derived from the affected household state rather than from changing forecast properties.

### Reason

A condition moving from six hours away to two hours away still represents the same underlying work.

Stable identity allows the existing task to be updated rather than duplicated.

---

## ADR-061: Predictive Tasks Are Reconciled Instead of Repeatedly Created

### Status

Accepted

### Decision

When a newly discovered predictive task has the same predictive task key as an existing task, the existing task is refreshed.

Changing properties may include:

- urgency
- confidence
- metadata
- intervention status
- time to threshold

### Reason

Forecasting can run repeatedly.

Without reconciliation, each evaluation could create another copy of the same household work.

---

## ADR-062: Non-Actionable Predictive Conditions Dismiss Existing Predictive Tasks

### Status

Accepted for MVP

### Decision

When an existing predictive task's intervention state changes to:

```text
MONITOR
```

or:

```text
NONE
```

the existing predictive task is dismissed rather than deleted.

### Reason

A previously actionable forecast may become non-actionable as new observations arrive.

Leaving the task pending would present stale work.

Deleting it would remove useful lifecycle information.

Dismissal represents the current decision while preserving the task object.

---

## ADR-063: Dismissed Predictive Tasks Can Be Reactivated

### Status

Accepted for MVP

### Decision

If a previously dismissed predictive condition later returns to:

```text
PLAN
```

or:

```text
ACT_NOW
```

the same logical predictive task can return to `PENDING`.

### Reason

Household conditions can improve and later deteriorate again.

The task lifecycle should represent this changing condition without producing unnecessary duplicate task identities.

---

## ADR-064: Predictive Task Lifecycle Does Not Imply Persistent Audit History Yet

### Status

Accepted

### Decision

The current in-memory task lifecycle supports creation, update, dismissal, and reactivation.

It does not claim to provide durable historical audit records.

### Reason

Persistent storage has not yet been implemented.

Lifecycle behavior can be tested in memory, but durable history requires a persistence model that will be designed separately.

---

## ADR-065: Reactive and Predictive Task Identity Are Not Yet Fully Unified

### Status

Open

### Decision

Reactive and predictive task discovery currently maintain their existing task-key behavior.

Cross-source reconciliation is intentionally deferred until the underlying task-key semantics are reviewed together.

### Reason

A reactive observation and a predictive intervention may eventually describe the same underlying household work.

Adding source-specific prefixes or changing task identity without reviewing both discovery paths could allow duplicates or incorrectly merge distinct tasks.

This should be resolved deliberately rather than hidden inside the forecasting implementation.
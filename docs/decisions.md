# HomHive Architecture Decisions

This document records important architectural decisions so they are not accidentally reversed in later development.

---

## ADR-001: Separate Observations from Tasks

### Status

Accepted

### Decision

An observation represents something HomHive has detected or learned about the household.

A task represents an action that may need to be performed.

These concepts must remain separate.

Example:

Observation:

`kitchen dish_load = 0.82`

Task:

`Clear the kitchen dishes`

### Reason

Perception should describe household conditions without deciding what action must immediately be taken.

This allows later reasoning and planning layers to determine whether an observation actually requires a task.

---

## ADR-002: Separate Observation History from Current State

### Status

Accepted

### Decision

HouseholdState maintains:

- `observation_history`
- `current_observations`

Observation history preserves observations over time.

Current observations contain the latest known observation for each location and category pair.

### Example

If HomHive receives:

`kitchen:dish_load = 0.82`

followed later by:

`kitchen:dish_load = 0.35`

observation history contains both values:

`0.82 -> 0.35`

while current state contains:

`kitchen:dish_load = 0.35`

### Reason

HomHive needs to answer two different questions:

1. What is happening now?
2. How has the household changed over time?

Historical data will later support forecasting, trend detection, and priority reasoning.

---

## ADR-003: Current State Uses Location and Category

### Status

Accepted

### Decision

Current observations are currently indexed using:

`location:category`

Example:

`kitchen:dish_load`

### Reason

Two observations of the same category may describe different parts of the home.

For example:

`kitchen:plant_condition`

and:

`bedroom:plant_condition`

must remain separate household states.

This representation may later be replaced by database identifiers or structured entity relationships as the storage layer becomes more sophisticated.

---

## ADR-004: Observation Values Use a Normalized Scale

### Status

Accepted for MVP

### Decision

Observation `value` currently uses a normalized range:

`0.0 <= value <= 1.0`

### Reason

A normalized representation provides a simple common interface for the initial household domains.

The exact semantic meaning of the value depends on the observation category.

This representation should be revisited when real perception outputs are integrated.

---

## ADR-005: Tasks Reference Source Observations by ID

### Status

Accepted

### Decision

Tasks contain:

`source_observation_id`

rather than embedding the complete Observation object.

### Reason

This preserves traceability without duplicating observation data inside every task.

It also prepares the data model for a future persistent database where observations and tasks can exist as separate records.

---

## ADR-006: External AI Services Are Not Part of the Core Data Models

### Status

Accepted

### Decision

Nebius, Tavily, LangSmith, Toloka, Tandem, and other external services should be integrated around the internal HomHive data contracts rather than directly embedded into them.

### Reason

HomHive's internal representations should remain stable even if models, providers, or external tools change.

The intended direction is:

External input / perception
        |
        v
Observation
        |
        v
Household State
        |
        v
Reasoning / Research
        |
        v
Task and Priority Plan

This keeps the core application architecture independent from individual AI providers.

---

## ADR-007: Use Deterministic Rules Before LLM Reasoning

### Status

Accepted

### Decision

Simple and well-defined task conditions should initially use deterministic rules instead of LLM reasoning.

For example:

`dish_load >= 0.70`

can deterministically produce a candidate dish-clearing task.

### Reason

Deterministic rules are faster, cheaper, predictable, and easy to test.

LLM reasoning should be reserved for situations where fixed rules are insufficient or the situation is ambiguous.

---

## ADR-008: Separate Task Discovery from Prioritization

### Status

Accepted

### Decision

Task discovery and task prioritization are separate responsibilities.

Task discovery answers:

`Does something need to be done?`

Prioritization answers:

`How important is this compared with other tasks?`

### Reason

A condition can justify creating a task without immediately determining its relative importance.

Separating these concerns allows the future priority engine to consider additional context such as deadlines, historical trends, consequences, effort, confidence, and user constraints.

---

## ADR-009: Use Stable Task Keys for Deduplication

### Status

Accepted

### Decision

Tasks contain a `task_key` representing the underlying work condition.

Current format:

`location:category`

Example:

`kitchen:dish_load`

The task `id` identifies a specific task instance.

The `task_key` identifies the underlying work condition.

### Reason

Multiple observations may describe the same unresolved condition.

If a task with the same `task_key` is already `pending` or `in_progress`, another task should not be created.

A `completed` or `dismissed` task does not prevent the same condition from generating a future task.

---

## ADR-010: Preserve Observations During Task Deduplication

### Status

Accepted

### Decision

Task deduplication does not deduplicate or remove observations.

Every valid observation continues to be stored in `observation_history`.

### Reason

Repeated observations may contain useful temporal information even when they refer to the same unresolved task.

Preserving them enables future:

- trend detection
- rate-of-change analysis
- forecasting
- temporal reasoning

---

## ADR-011: Use Frozen Dataclasses for Static Task Rules

### Status

Accepted

### Decision

Static task-discovery rules use a frozen Python `dataclass`.

A `TaskRule` currently contains:

- `threshold`
- `description`
- `effort_minutes`

### Reason

Task rules are internal application configuration rather than external data contracts.

A frozen dataclass provides a lightweight structured representation and prevents accidental mutation.

Pydantic remains responsible for runtime-validated domain models such as `Observation`, `HouseholdState`, and `Task`.

---

## ADR-012: Confidence Thresholds Are Category-Specific

### Status

Accepted

### Decision

Minimum observation confidence is stored as part of each `TaskRule` rather than using one global confidence threshold.

### Reason

Different observation categories may eventually require different levels of certainty.

For example, a simple dish-load observation may tolerate more uncertainty than a future maintenance or safety-related observation.

---

## ADR-013: Low-Confidence Observations Are Preserved

### Status

Accepted

### Decision

Observations that fail the task-discovery confidence threshold remain part of household state and observation history.

### Reason

Insufficient confidence for action does not make an observation useless.

Historical uncertain evidence may later support temporal reasoning, trend analysis, evaluation, or evidence aggregation.

---

## ADR-014: Repeated Uncertain Observations Do Not Automatically Increase Confidence

### Status

Accepted for MVP

### Decision

Multiple low-confidence observations do not automatically combine into a high-confidence decision.

### Reason

Repeated observations may share the same source of error, such as poor lighting, camera angle, or perception-model failure.

Evidence aggregation should be implemented explicitly rather than implicitly inside task discovery.

---

## ADR-015: Task Discovery Decisions Are Explainable

### Status

Accepted

### Decision

Detailed task discovery returns a structured `TaskDiscoveryResult` containing:

- task
- reason

Current reasons include:

- task_created
- unsupported_category
- below_threshold
- low_confidence
- duplicate_active_task

### Reason

The system should represent why it acted or why it chose not to act.

Structured decision reasons support debugging, evaluation, observability, future UI explanations, and tracing.

---

## ADR-016: Preserve the Simple Task Discovery Interface

### Status

Accepted

### Decision

`discover_task_detailed()` provides the richer decision result.

`discover_task()` remains available and returns:

`Task | None`

### Reason

This preserves backward compatibility while allowing newer components to consume richer decision information.

---

## ADR-017: Prioritization Is Separate from Task Discovery

### Status

Accepted

### Decision

Task discovery and task prioritization are implemented as separate system layers.

### Reason

Discovery determines whether work exists.

Prioritization determines the relative importance of discovered work.

Keeping these concerns separate allows prioritization to change without changing task identity or discovery behavior.

---

## ADR-018: Priority Is Dynamic State, Not Task Identity

### Status

Accepted

### Decision

Priority scores are stored in `PrioritizedTask` rather than directly on `Task`.

### Reason

The underlying task may remain unchanged while its priority changes because of time, confidence, forecasts, deadlines, or other contextual information.

---

## ADR-019: Deterministic Priority Scoring Precedes LLM Reasoning

### Status

Accepted

### Decision

Initial priority scoring uses deterministic signals and explicit weights.

Current signals are:

- urgency
- confidence
- effort efficiency

### Reason

Simple ranking behavior should remain predictable, testable, and inexpensive.

Future AI reasoning can augment the deterministic baseline when contextual decisions require richer reasoning.

---

## ADR-020: Effort Has Limited Influence on Priority

### Status

Accepted

### Decision

Effort efficiency contributes 10% of the current priority score.

### Reason

Short tasks may be easier to schedule, but convenience should not dominate importance.

Urgency remains the strongest current signal.

---

## ADR-021: Priority Ties Use a Deterministic Fallback

### Status

Accepted for MVP

### Decision

Tasks with equal priority scores are ordered by task ID.

### Reason

Input ordering from databases or APIs should not accidentally determine the action plan.

Task ID is only a reproducibility mechanism and may later be replaced by a meaningful temporal signal.

## ADR-022: Derived state is separate from raw observations

### Decision
Raw observations remain preserved in `HouseholdState.observation_history`, while `AggregatedState` represents the system's derived belief about the current condition.

### Why
A single observation is evidence, not necessarily the true current state. Separating evidence from derived state allows multiple observations to contribute to the system's current belief without destroying historical information.

---

## ADR-023: State aggregation uses confidence and recency

### Decision
Observation influence is calculated using:

`observation_weight = confidence * recency_weight`

where:

`recency_weight = 1 / (1 + age_hours)`

### Why
Newer observations should generally influence current state more strongly, but a recent low-confidence observation should not automatically replace older high-confidence evidence.

---

## ADR-024: State identity uses location and category

### Decision
Observations are grouped using:

`location + category`

Example:

`kitchen:dish_load`

### Why
The same observation category can exist independently in different locations. Kitchen dishes and dining-room dishes must not be treated as the same state.

---

## ADR-025: Trend detection is deterministic and threshold-based

### Decision
Trend direction is classified as:

- `UNKNOWN` when fewer than two observations exist
- `STABLE` when absolute change is less than or equal to `0.05`
- `RISING` when change is greater than the stable threshold
- `FALLING` when change is less than the negative stable threshold

Observations are ordered by timestamp before trend calculation.

### Why
The MVP needs explainable trend information without introducing forecasting or statistical models prematurely. Timestamp ordering also prevents input-list order from affecting the result.

---

## ADR-026: Floating-point trend comparisons are normalized

### Decision
Absolute trend change is rounded to four decimal places before comparison with the stable threshold.

### Why
Binary floating-point representation can produce values such as `0.050000000000000044` for a conceptual change of `0.05`. This should not change the intended classification at the stability boundary.

---

## ADR-027: Aggregated confidence is not accumulated

### Decision
For the current MVP, aggregated-state confidence uses the maximum confidence among contributing observations rather than increasing confidence based on observation count.

### Why
Repeated observations may contain correlated errors. Multiple uncertain observations should not automatically create artificial confidence. More sophisticated confidence aggregation can be evaluated later.

## ADR-028: Household entities are modeled separately from observations.

### Decision:
Persistent physical things are represented by HouseholdEntity rather than
embedding identity information directly into observations.

### Reason:
Entity identity and observed condition have different lifecycles. The same
entity can accumulate many observations over time.


## ADR-029: Entity type and specific identity are separate.

### Decision:
HouseholdEntity uses a broad EntityType while identity stores the optional
specific recognized identity.

Example:
entity_type = PLANT
identity = "Monstera deliciosa"

### Reason:
The system may know that an object is a plant before knowing its exact species.


## ADR-030: Identification confidence is separate from observation confidence.

### Decision:
HouseholdEntity stores identification_confidence independently from
Observation.confidence.

### Reason:
Confidence that an object is a Monstera is different from confidence that
its leaves appear unhealthy.


## ADR-031: Observations may optionally reference entities.

### Decision:
Observation.entity_id is optional.

### Reason:
Observations must be representable before entity identification succeeds,
and some observations may describe locations or conditions without a
specific entity.


## ADR-032: Entity identity takes precedence in state keys.

### Decision:
When entity_id exists, state identity uses:

entity_id:category

Otherwise it falls back to:

location:category

### Reason:
Multiple entities of the same category may exist in the same location.


## ADR-033: State-key policy has one source of truth.

### Decision:
Observation.state_key() owns state identity construction.

HouseholdState and temporal aggregation reuse that policy.

### Reason:
This prevents different parts of the system from generating incompatible
state identities.


## ADR-034: Entity attributes remain extensible.

### Decision:
Entity-specific intrinsic properties are stored in attributes rather than
adding every possible plant, appliance, area, or fixture property to the
core model.

### Reason:
Different entity types require different properties while the core entity
contract should remain stable.


## ADR-035: External entity knowledge is not part of HouseholdEntity.

### Decision:
Web-researched care instructions, manuals, maintenance guidance, and similar
knowledge are not stored directly in the core HouseholdEntity contract.

### Reason:
"What is this physical thing?" and "What external knowledge do we have about
this type of thing?" are separate concerns.
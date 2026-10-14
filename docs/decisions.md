# HomHive Architecture Decisions

This register records active architecture boundaries and unresolved design choices. Implementation chronology belongs in Git history.

## Domain boundaries

### ADR-001: Observation and task are different concepts

**Status:** Accepted

An observation describes household evidence.

A task describes work that may need to be performed.

```text
Observation: kitchen dish_load = 0.82
Task: clear the dishes in the kitchen
```

### ADR-002: Preserve history separately from current state

**Status:** Accepted

`HouseholdState` retains observation history while also providing current observations.

Historical evidence must not be destroyed simply because a newer observation exists.

### ADR-003: Observation values use a normalized MVP scale

**Status:** Accepted for MVP

Condition values currently use:

```text
0.0 <= value <= 1.0
```

The semantic meaning remains condition-specific.

### ADR-004: External providers do not belong in core domain models

**Status:** Accepted

Tavily, Nebius, Nemotron, LangSmith, vision providers, and other external tools must integrate through adapters around stable HomHive contracts.

## State and condition tracking

### ADR-005: Raw evidence and derived state stay separate

**Status:** Accepted

`Observation` is raw evidence.

`ConditionSnapshot` is the derived current belief.

### ADR-006: State aggregation uses confidence and recency

**Status:** Accepted

Current deterministic weighting is:

```text
recency_weight = 1 / (1 + age_hours)
observation_weight = confidence * recency_weight
```

### ADR-007: Trend detection remains deterministic

**Status:** Accepted for MVP

`ConditionTrend` is derived from ordered observations with a small stable-change boundary.

### ADR-008: Repeated uncertain evidence does not automatically become certain

**Status:** Accepted

Observation count alone must not inflate confidence because errors can be correlated.

### ADR-009: State-key construction has one source of truth

**Status:** Accepted

`Observation.state_key()` owns condition identity construction.

Entity identity takes precedence when available. Location is the fallback.

## Reactive work

### ADR-010: Deterministic rules come before LLM reasoning

**Status:** Accepted

Simple household conditions should be handled with predictable code.

### ADR-011: Reactive rules are represented by `TaskTrigger`

**Status:** Accepted

The canonical reactive configuration object is `TaskTrigger`.

### ADR-012: Confidence thresholds are condition-specific

**Status:** Accepted

Different condition types may require different confidence before creating work.

### ADR-013: Low-confidence observations remain stored

**Status:** Accepted

Evidence can be useful for state/history even when it is too weak for action.

### ADR-014: Task discovery decisions are explainable

**Status:** Accepted

`TaskDecision` and `TaskDecisionReason` represent why work was or was not created.

### ADR-015: Active work is deduplicated by stable task identity

**Status:** Accepted

Repeated observations should not create repeated unresolved reactive tasks.

## Task and priority

### ADR-016: Task discovery and ranking are separate responsibilities

**Status:** Accepted

Discovery answers:

```text
Does work exist?
```

Ranking answers:

```text
How should existing work be ordered?
```

### ADR-017: Priority is dynamic state

**Status:** Accepted

A `Task` does not own a permanent priority score.

`ScoredTask` represents task plus current planning score.

### ADR-018: Deterministic ranking is the baseline

**Status:** Accepted

Current weights:

```text
urgency   0.60
confidence 0.30
effort     0.10
```

### ADR-019: Equal scores use deterministic ordering

**Status:** Accepted for MVP

Task ID provides a stable fallback ordering.

## Household entities

### ADR-020: Physical entities are separate from observations

**Status:** Accepted

`HouseholdEntity` represents a persistent physical thing.

Observations describe changing condition about an entity or location.

### ADR-021: Entity type and exact identity are different

**Status:** Accepted

The system can know something is a plant before knowing the species.

### ADR-022: Identification confidence is separate from condition confidence

**Status:** Accepted

Confidence that an object is a Monstera is not the same as confidence that its leaves look unhealthy.

### ADR-023: Identification produces candidates

**Status:** Accepted

Perception should produce an `EntityCandidate` rather than directly mutating persistent household identity.

### ADR-024: Compatibility is not physical identity

**Status:** Accepted

Type, location, and identity compatibility only narrow possible matches.

### ADR-025: Missing evidence and contradictory evidence are different

**Status:** Accepted

An unavailable attribute must not be treated as a mismatch.

### ADR-026: Contradictory shared evidence blocks strong automatic matching

**Status:** Accepted for MVP

HomHive should prefer uncertainty over silently attaching evidence to the wrong physical object.

### ADR-027: Entity resolution is conservative

**Status:** Accepted

The resolution pipeline may return a match, creation outcome, or uncertainty rather than forcing a binary answer.

## Forecasting

### ADR-028: Current state and forecast are different models

**Status:** Accepted

`ConditionSnapshot` describes current derived state.

`ConditionForecast` describes a future projection.

### ADR-029: Forecast confidence is separate from snapshot confidence

**Status:** Accepted

A strong current observation does not automatically imply a strong long-horizon forecast.

### ADR-030: Threshold crossing is a separate domain event

**Status:** Accepted

A forecast does not imply that an action threshold will be crossed.

`ThresholdCrossing` represents that specific prediction.

### ADR-031: Flat or improving conditions do not predict an upper-threshold crossing

**Status:** Accepted for the deterministic MVP

The current threshold estimator only predicts a future upper crossing when the modeled condition is moving toward it.

## Predictive action

### ADR-032: Forecasting and action policy are separate

**Status:** Accepted

Forecasting describes what is expected to happen.

`ActionDecision` describes how HomHive should react to that forecast.

### ADR-033: Weak predictions may be monitored without creating work

**Status:** Accepted

Low-confidence forecasts remain visible but should not automatically create household tasks.

### ADR-034: Action states are explicit

**Status:** Accepted

Canonical states:

```text
NONE
MONITOR
PLAN
ACT_NOW
```

### ADR-035: Predictive tasks have lifecycle

**Status:** Accepted

Predictive work can be created, updated, dismissed, and later reactivated.

### ADR-036: Predictive tasks may not have one source observation

**Status:** Accepted

Forecasts are derived from multiple observations, so `source_observation_id` may be `None`.

## API and storage

### ADR-037: API, application service, repository, and domain model are separate layers

**Status:** Accepted

GraphQL should not contain repository or domain-policy logic.

### ADR-038: Public GraphQL names may remain stable while Python names improve

**Status:** Accepted

Internal cleanup should not casually break public API contracts.

### ADR-039: Storage implementations remain behind repository contracts

**Status:** Accepted

Household entity, observation, and task storage can use in-memory or SQLAlchemy implementations. ORM records remain separate from Pydantic domain models. Household-scoped evidence review and intelligence refresh use observation and task repositories without exposing ORM records to application services.

## AI integration

### ADR-040: Vision extracts evidence, not final plans

**Status:** Accepted

The perception layer should produce structured observations and identity clues.

### ADR-041: Tavily is conditional

**Status:** Accepted and implemented

Do not search the web for every routine observation.

### ADR-042: Stable verified entity knowledge should eventually be reusable

**Status:** Accepted as target design

Repeated identification/research should be avoided where trustworthy cached knowledge exists.

### ADR-043: Nemotron reasons over structured facts

**Status:** Accepted and implemented behind configuration

The reasoning model should not act as the database or invent raw household state.

## Naming

### ADR-044: Canonical vocabulary is now stable

**Status:** Accepted

Canonical names include:

```text
ConditionType
ConditionSnapshot
ConditionTrend
TaskUrgency
TaskDecision
ScoredTask
ConditionForecast
ThresholdCrossing
ActionDecision
```

Compatibility names removed during the refactor should not be reintroduced without a concrete external-contract reason.

## Open decisions

### ADR-045: Cross-source task identity

**Status:** Open

Reactive and predictive tasks currently use different task-key approaches.

The system still needs an explicit policy for deciding whether a reactive observation and a predictive forecast represent the same underlying household work.

Do not silently unify these identities during unrelated changes.

### ADR-046: Durable evidence and work storage

**Status:** Partially resolved

PostgreSQL tables, Alembic migrations, and repository contracts exist for entities, household-scoped observations, and household-scoped tasks. `HouseholdState` is reconstructed from persisted observations; derived snapshots are not authoritative database records. Full audit events, retention policy, and atomic concurrency-safe workflow processing remain open.

### ADR-047: User context and executability

**Status:** Partially implemented

Future planning should distinguish:

```text
importance != executability != fit
```

Being at home does not automatically mean being available, and free time does not automatically mean a household task fits that window.

## Media storage and access

### ADR-048: Media bytes and metadata are stored separately

**Status:** Accepted

`LocalMediaStorage` stores uploaded image bytes beneath a private, configurable filesystem root using a household ID and media ID. PostgreSQL persists `MediaRecord` metadata keyed by `(household_id, id)`. The media service coordinates both writes and removes a newly stored file when metadata persistence fails. Images are not stored in the observation domain model, and this storage separation alone does not guarantee production security.

### ADR-049: Media reads and writes require household-scoped authorization

**Status:** Accepted for local development

Media HTTP endpoints require a bearer token matching the requested household. The record lookup is also scoped to the household ID, so possession of a valid token for another household does not return media owned by the first. The current JSON token mapping is a development mechanism, not a final user identity or household membership system. The API does not expose stored images as public static files.

## Vision and evidence uncertainty

### ADR-050: Unknown observation confidence is explicit

**Status:** Accepted

An observation may have `confidence=None` when no calibrated confidence estimate exists. PostgreSQL stores this as `NULL`; schema migration `0005_unknown_confidence` changes the column to nullable. Unknown must not be replaced with an arbitrary default, conflated with `0.0`, or interpreted as permission to trigger tasks. Derived confidence calculations and action gates handle unknown input explicitly. The implementation uses an Alembic batch operation compatible with SQLite-backed migration tests.

### ADR-051: Vision output is evidence, not authority

**Status:** Accepted

Vision providers produce structured candidates and directly visible evidence. Provider output is validated before mapping into HomHive's domain model. Nonvisible household domains are omitted rather than recorded as zero conditions; review-needed results are not persisted. Each persisted photo observation records its household-scoped source media ID and visible evidence. This stage does not automatically create tasks.

### ADR-052: Dish-load measures visible dishwashing workload

**Status:** Accepted as a working semantic definition; calibration pending

The normalized `dish_load` value refers to visible accumulated dishwashing work, not simply the percentage of sink area occupied. A model output of `1.0` represents the top of its proposed workload scale, not a verified physical capacity measurement. Thresholds and numeric calibration require a reproducible evaluation set before claiming model accuracy.

### ADR-053: Vision inference is household-authorized and opt-in

**Status:** Accepted

The vision API is enabled only when media storage, household token configuration, database access, and `NEBIUS_API_KEY` are configured. It requires matching household bearer authorization and resolves stored media within that household before using an external inference provider. The development bearer-token mechanism is not production user authentication.

## Scene understanding and evaluation

### ADR-054: Separate visible object inventory from condition-derived observations

**Status:** Accepted for experimental read-only evaluation

A scene may contain many visible household objects regardless of whether they need attention. Scene inventory records visible labels, placements, and evidence independently of household `Observation` and task generation. The existing observation persistence path stays unchanged while completeness and condition accuracy are unverified. Physical entity identity across images is not inferred or stored at this stage.

### ADR-055: Invalid condition evidence must not erase otherwise valid object detections

**Status:** Accepted

An assessed condition must have explicit evidence. If a structurally valid detected object has an assessed condition with missing evidence, retain the object as `unknown`, record the claimed condition under `rejected_assessments`, and set `needs_review`. Trusted location comes from the application request. Unknown/unassessed condition evidence may narrowly normalize literal `"null"` to JSON null. Invalid objects, unsupported attributes, or mismatched locations remain rejected. This is not model-confidence calibration.

### ADR-056: Treat schema-valid vision output separately from measured completeness

**Status:** Accepted

Unit-test success and valid JSON do not establish visual recall. Retain development evaluation reports and failures, measure completion independently of accuracy, and use manually labeled unseen images to assess scene object recall and false positives. The first live read-only inventory returned only a drain and therefore does not support a completeness claim.


### ADR-057: Separate scene discovery from condition assessment when measuring completeness

**Status:** Accepted

Object discovery and condition assessment are distinct perception responsibilities. A detection-first scene mode can enumerate visible entities without forcing the model to assign a condition. Completeness is measured against a human-reviewed reference inventory before condition accuracy is considered.

### ADR-058: User confirmation adds evidence instead of rewriting AI evidence

**Status:** Accepted

When an AI observation has unknown confidence and requires confirmation, the original provider observation remains unchanged. Confirmation creates separate user-sourced evidence. This preserves provenance and avoids manufacturing confidence that the provider did not supply.

### ADR-059: Deterministic feasibility constrains model planning

**Status:** Accepted

Available active time, passive time, at-home requirements, quiet hours, and explicit task limits are deterministic constraints. NVIDIA Nemotron can reason over the remaining feasible work, but returned task IDs and selections are validated before acceptance. Model output cannot override a hard feasibility block.

### ADR-060: External research is untrusted, normalized, and household-scoped

**Status:** Accepted

Tavily results are external evidence, not household truth. Provider-specific responses are normalized into HomHive research models, source metadata is retained, and durable cache entries are scoped by household. Research is conditional and should not be invoked for routine facts already represented by deterministic household logic.

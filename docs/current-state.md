# HomHive Current State

Last updated: September 23, 2026

## Current Milestone

Day 6 of the 38-day HomHive build roadmap.

Focus: Temporal state aggregation, confidence and recency weighting, conflict handling, and trend detection.

### Day 1

- Initialized HomHive Git repository.
- Created initial project structure.
- Added backend and frontend directories.
- Added sample-data structure.
- Added evaluation structure.
- Added project documentation:
  - architecture.md
  - evaluation.md
  - hackathon.md
  - product-spec.md
- Added README and MIT license.
- Added project .gitignore.

### Day 2

#### Backend Structure

Created Python application structure under:

`backend/app/`

Created model package:

`backend/app/models/`

#### Observation Model

Implemented a Pydantic Observation model containing:

- id
- source
- location
- category
- value
- confidence
- timestamp
- metadata

Observation values and confidence are validated between 0.0 and 1.0.

Supported observation sources:

- photo
- video
- user_input
- history
- external_research

Initial observation categories:

- dish_load
- laundry_load
- plant_condition
- lawn_condition
- maintenance_status

#### Household State

Implemented `HouseholdState`.

Household state separates:

- `observation_history`
- `current_observations`

Observation history preserves observations over time.

Current observations contain the latest known observation for each location and category pair.

Current-state keys use:

`location:category`

Example:

`kitchen:dish_load`

When a newer observation for the same location and category arrives, the current observation is replaced while previous observations remain in history.

#### Task Model

Implemented a Pydantic `Task` model containing:

- id
- task_key
- description
- source_observation_id
- urgency
- estimated_effort_minutes
- deadline
- confidence
- status
- created_at
- metadata

Task urgency supports:

- low
- medium
- high
- critical

Task status supports:

- pending
- in_progress
- completed
- dismissed

#### Python Environment

Created an isolated Python virtual environment:

`backend/.venv/`

The virtual environment is excluded from Git.

Created:

`backend/requirements.txt`

Current declared dependencies:

- pydantic
- pytest

### Day 3

#### Service Layer

Created:

`backend/app/services/`

Added:

- `__init__.py`
- `task_discovery.py`

This separates application behavior from the core data models.

#### Deterministic Task Discovery

Implemented task discovery that converts qualifying observations into candidate tasks.

Current rules:

- `dish_load >= 0.70`
  - Creates a dish-clearing task
  - Estimated effort: 15 minutes

- `laundry_load >= 0.75`
  - Creates a laundry task
  - Estimated effort: 45 minutes

Categories without configured rules currently produce no task.

Task discovery is deterministic at this stage. LLM reasoning is not required for simple, well-defined conditions.

#### Task Rules

Introduced a frozen `TaskRule` dataclass containing:

- threshold
- description
- effort_minutes

This separates task-discovery policy from the discovery mechanism.

#### Task Identity

Added `task_key` to the `Task` model.

Example:

`kitchen:dish_load`

`id` identifies a specific task instance.

`task_key` identifies the underlying work condition and is used for duplicate detection.

#### Duplicate Task Prevention

`discover_task()` now accepts existing tasks.

If a task with the same `task_key` is already:

- pending
- in_progress

a duplicate task is not created.

If the previous task is:

- completed
- dismissed

a new task may be created when the condition occurs again.

Observation history remains independent from task deduplication.

#### End-to-End State Flow

Added a test covering a sequence where:

1. Dish load starts below the task threshold.
2. Dish load increases and creates a task.
3. Another observation of the unresolved condition does not create a duplicate.
4. The original task is completed.
5. The condition occurs again and creates a new task.
6. All observations remain in history.
7. Current state points to the latest observation.

This verifies behavior across time rather than only testing isolated models.

#### Testing

Current test files include:

- `test_observation.py`
- `test_household_state.py`
- `test_task.py`
- `test_task_discovery.py`
- `test_task_discovery_flow.py`

Current result:

**21 tests passing**

Tests currently cover:

- Observation validation
- Enum validation
- Task validation
- Household-state updates
- Observation history preservation
- Current-state replacement
- Dish task discovery
- Laundry task discovery
- Threshold behavior
- Unsupported task categories
- Task-key generation
- Pending-task deduplication
- In-progress-task deduplication
- Re-creation after task completion
- Different task-key handling
- Multi-observation state-to-task flow

## Current Architecture

The implemented system currently contains two connected deterministic flows.

### State Understanding

Observation

    ↓

HouseholdState

    +-- observation_history

    +-- current_observations

    ↓

State Aggregation

    +-- confidence weighting

    +-- recency weighting

    +-- conflict handling

    +-- trend detection

    ↓

AggregatedState


### Task Decision Flow

Observation

    ↓

Task Discovery

    +-- category rule

    +-- value threshold

    +-- confidence threshold

    +-- duplicate detection

    ↓

TaskDiscoveryResult

    +-- task

    +-- reason

    ↓

Candidate Tasks

    ↓

Priority Scoring

    +-- urgency

    +-- confidence

    +-- effort efficiency

    ↓

Ordered Action Plan

The state-understanding and task-decision flows are not yet fully connected.

Task discovery currently operates on observations rather than derived `AggregatedState`.

Future work will determine how derived state, trends, forecasting, and contextual reasoning influence task creation and prioritization.

The following major layers have not yet been implemented:

- household entity identification
- perception
- forecasting
- external research
- LLM reasoning
- persistence/database
- API layer
- calendar and personal-context integration
- presence and availability reasoning
- frontend integration

## External Services Available

Credits/access are available for:

- Nebius
- Tavily
- LangSmith
- Toloka
- Tandem

These services have not yet been integrated.

Planned high-level roles:

- Nebius: model inference and core reasoning
- Tavily: external research when internal context is insufficient
- LangSmith: AI workflow tracing and evaluation
- Toloka: potential human evaluation/data validation
- Tandem: role to be determined based on available capabilities

### Day 4

#### Confidence-Aware Task Discovery

Extended task discovery to consider observation confidence in addition to the observed value.

Each `TaskRule` now contains:

- threshold
- min_confidence
- description
- effort_minutes

Current dish and laundry rules require a minimum confidence of `0.70`.

A task is created only when both the condition threshold and confidence threshold are satisfied.

#### Confidence Handling

Current behavior:

- High value + high confidence -> task
- High value + low confidence -> no task
- Low value + high confidence -> no task
- Confidence exactly at the minimum threshold -> accepted

Low-confidence observations are still preserved in household history and current state even when they do not produce tasks.

Repeated low-confidence observations do not automatically combine into higher confidence.

A later high-confidence observation can independently trigger a task.

#### Explainable Discovery Results

Added:

`backend/app/models/task_discovery_result.py`

Introduced:

- `TaskDiscoveryResult`
- `TaskDiscoveryReason`

Current discovery reasons:

- `task_created`
- `unsupported_category`
- `below_threshold`
- `low_confidence`
- `duplicate_active_task`

Added:

`discover_task_detailed()`

This returns both the discovered task and the reason for the decision.

The existing `discover_task()` interface remains available and continues returning:

`Task | None`

This preserves backward compatibility for existing callers.

#### Testing

Added coverage for:

- high-value/high-confidence observations
- high-value/low-confidence observations
- low-value/high-confidence observations
- confidence boundary behavior
- repeated uncertain observations
- recovery from uncertain to reliable evidence
- successful task creation reason
- below-threshold reason
- low-confidence reason
- unsupported-category reason
- duplicate-active-task reason

### Day 5

#### Task Prioritization

Added a prioritization layer separate from task discovery.

Task discovery answers:

"What work exists?"

Task prioritization answers:

"What should happen first?"

Added:

`backend/app/models/task_priority.py`

with:

- `PrioritizedTask`
- `priority_score`

Priority is intentionally kept separate from the core `Task` model because priority can change as context changes while the underlying task remains the same.

#### Priority Signals

The current deterministic MVP uses three signals:

- urgency
- confidence
- effort efficiency

Current weighting:

- urgency: 60%
- confidence: 30%
- effort efficiency: 10%

Urgency mapping:

- LOW = 0.25
- MEDIUM = 0.50
- HIGH = 0.75
- CRITICAL = 1.00

Effort normalization:

`1 / (1 + effort_minutes / 30)`

The weights are MVP heuristics and should be evaluated and tuned later rather than treated as objectively correct.

#### Ranking

Added:

`backend/app/services/task_prioritization.py`

The service can:

- calculate effort scores
- calculate priority scores
- prioritize individual tasks
- rank collections of tasks

Tasks are ordered by descending priority score.

Equal scores use task ID as a deterministic fallback tie-breaker.

Task ID is not considered a measure of importance. It is only used to guarantee reproducible ordering until a meaningful temporal tie-breaker is introduced.

### Day 6

#### Temporal State Aggregation

Added a derived-state layer that converts observation history into a current belief about each household condition.

Added:

`backend/app/models/aggregated_state.py`

with:

- location
- category
- current_value
- confidence
- trend
- latest_observation
- observation_count
- updated_at

`AggregatedState` is intentionally separate from raw `Observation` data.

An observation represents evidence captured at a specific point in time.

An aggregated state represents the system's current derived belief after considering multiple observations.

#### Confidence and Recency Weighting

Added:

`backend/app/services/state_aggregation.py`

Observation influence is calculated using:

`observation_weight = confidence * recency_weight`

Current recency function:

`recency_weight = 1 / (1 + age_hours)`

This gives newer observations greater influence while still allowing older high-confidence evidence to contribute to the current state.

A recent low-confidence observation therefore does not automatically replace older reliable evidence.

The aggregated current value is calculated as a weighted average:

`sum(value * weight) / sum(weight)`

#### Aggregated Confidence

Current MVP aggregated confidence uses the maximum confidence among contributing observations.

Repeated observations do not automatically increase confidence.

This is intentionally conservative because multiple observations may contain correlated errors.

A more sophisticated confidence model may be introduced after evaluation.

#### State Grouping

Added:

`aggregate_household_state()`

Observation history is grouped using:

`location:category`

Examples:

`kitchen:dish_load`

`laundry_room:laundry_load`

This allows multiple observations of the same condition to contribute to one derived state while keeping different locations and categories independent.

An empty household state produces an empty aggregation rather than inventing zero-valued conditions.

#### Trend Detection

Added temporal trend classification using `TrendDirection`.

Supported directions:

- rising
- stable
- falling
- unknown

Trend calculation sorts observations by timestamp before comparing the oldest and newest values.

This means trend behavior does not depend on the order in which observations are supplied to the function.

With fewer than two observations, trend is:

`unknown`

Current stability threshold:

`0.05`

Changes with an absolute magnitude less than or equal to the threshold are classified as stable.

Larger positive changes are classified as rising.

Larger negative changes are classified as falling.

This is intentionally a simple deterministic MVP heuristic rather than a forecasting model.

#### Floating-Point Boundary Handling

Trend change is rounded to four decimal places before comparison with the stability threshold.

This prevents binary floating-point representation from incorrectly classifying a conceptual change of exactly `0.05` as slightly greater than `0.05`.

## Day 7 - Household Entity Model

Implemented persistent household entity representation.

### Added

- EntityType enum
- HouseholdEntity model
- optional specific entity identity
- identification confidence
- extensible entity attributes
- optional Observation.entity_id
- entity-aware state identity
- Observation.state_key() as the canonical state-key policy

### Entity-aware state tracking

State identity now follows:

entity_id + category
when an entity is known

location + category
when no entity is associated

This prevents multiple physical entities of the same category in the same
location from being merged into one state stream.

### Current Entity Flow

HouseholdEntity
    ↓ entity_id
Observation
    ↓ state_key()
HouseholdState
    ↓
Temporal State Aggregation
    ↓
AggregatedState

Entity identification itself is not implemented yet.

### Testing

77 automated tests passing.

Coverage added for:

- basic entity creation
- unknown entity identity
- identified entities
- entity attributes
- identification confidence bounds
- required name/location
- optional observation-to-entity references
- entity-aware state keys
- multiple entities in the same location
- independent entity attribute dictionaries

## Next

Day 8 - Entity Identification Workflow
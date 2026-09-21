# HomHive Current State

Last updated: September 19, 2026

## Current Milestone

Day 5 of the 38-day HomHive build roadmap.

Focus: Deterministic task prioritization and ordered action planning.

## Completed

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

The implemented system currently looks like:

Observation
    |
    v
HouseholdState
    |
    +-- observation_history
    |
    +-- current_observations
    |
    v
Task Discovery
    |
    +-- category rule
    +-- value threshold
    +-- confidence threshold
    +-- duplicate detection
    |
    v
TaskDiscoveryResult
    |
    +-- task
    +-- reason

The current implementation can represent observations, maintain historical and current state, discover basic tasks, and prevent duplicate active tasks.

The following layers have not yet been implemented:

- perception
- LLM reasoning
- prioritization
- forecasting
- external research
- persistence/database
- API layer
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

#### Current Pipeline

Observation
    ↓
HouseholdState
    ↓
Task Discovery
    ↓
Candidate Tasks
    ↓
Priority Scoring
    ↓
Ordered Action Plan

Urgency is currently assigned manually or defaults to MEDIUM.

Automatic urgency inference has not yet been implemented.

#### Testing

Added tests for:

- effort normalization
- shorter versus longer effort
- priority score bounds
- urgency influence
- confidence influence
- prioritized task creation
- urgency versus effort behavior
- multi-task ranking
- empty task collections
- deterministic tie-breaking
- observation-to-prioritized-plan integration

Current result:

**43 tests passing**

## Current Test Status

**43 passed**

## Current Blockers

None.

## Next

Continue to Day 6 of the HomHive roadmap.

The current system supports structured observations, temporal state, confidence-aware task discovery, explainable discovery outcomes, duplicate prevention, deterministic priority scoring, and ordered action planning.

Urgency inference, forecasting, external AI reasoning, research, persistence, APIs, perception, and frontend integration remain future layers.
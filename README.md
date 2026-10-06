# HomHive

> **The intelligence layer for the autonomous home.**

HomHive is a household intelligence and orchestration system designed to understand how a home changes over time, discover work without requiring every task to be manually entered, predict when conditions may become actionable, and help determine what should happen next.

The project is currently being built as a tested backend-first system. The implemented foundation focuses on household state, task discovery, temporal reasoning, entity identity, forecasting, and predictive task lifecycle before connecting perception and LLM-based reasoning.

## Vision

Homes continuously generate work.

Dishes accumulate. Laundry fills up. Plants need attention. Lawns grow. Filters become overdue. Food approaches expiration. Maintenance tasks appear over time.

Traditional task-management systems generally depend on someone noticing a condition, creating a task, deciding how urgent it is, and remembering when it needs attention.

HomHive explores a different model:

```text
Observe the home
      ↓
Understand current state
      ↓
Track how that state changes
      ↓
Discover or predict work
      ↓
Decide when intervention is justified
      ↓
Prioritize what should happen next
```

The longer-term goal is for the same intelligence layer to coordinate work performed by people, smart appliances, autonomous systems, or household robots.

---

## Core Questions

HomHive is being designed around three questions:

1. **What needs to be done?**
2. **When does it need to be done?**
3. **Who or what should do it?**

Example:

```text
Kitchen dishes       High load
Laundry              72% full
Plant                Appears dry
Lawn                 Moderate growth
HVAC filter          Approaching service interval
                     ↓
                  HomHive
                     ↓
TODAY
1. Check and water plant
2. Clear kitchen sink

THIS WEEK
3. Laundry
4. Lawn maintenance

UPCOMING
5. HVAC filter replacement
```

This example represents the product direction. Not every domain shown above is implemented yet.

---

## Current Architecture

The current backend has two related paths: immediate deterministic task discovery and temporal predictive reasoning.

```text
                         Observations
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
           Household State         Reactive Rules
                  │                       │
                  ▼                       ▼
          State Aggregation          Candidate Task
                  │
                  ▼
              Forecast
                  │
                  ▼
        Threshold Prediction
                  │
                  ▼
        Intervention Decision
                  │
                  ▼
         Predictive Task
                  │
                  ▼
        Task Reconciliation
                  │
                  └───────────┐
                              ▼
                            Tasks
                              │
                              ▼
                       Prioritization
```

The system is intentionally being built as separate, testable layers before external AI services are introduced.

See `docs/architecture.md` for the detailed architecture.

---

## Implemented So Far

### Household State

HomHive can represent observations from sources including:

- photos
- videos
- user input
- historical state
- external research

The current backend stores observation history separately from the latest known state.

Raw observations remain available for temporal analysis.

---

### Deterministic Task Discovery

Simple conditions can create tasks without requiring an LLM.

Task discovery currently supports:

- category-specific thresholds
- confidence requirements
- duplicate prevention
- structured decision reasons

The rule-based layer is intended to handle predictable cases before more expensive reasoning is introduced.

---

### Task Prioritization

Discovered tasks can be ranked using a deterministic baseline based on:

- urgency
- confidence
- effort

The current weights are MVP heuristics and are expected to change after evaluation.

---

### Temporal State Aggregation

Multiple observations can be combined into a derived current state using:

```text
observation weight
=
confidence × recency
```

The system also tracks whether a condition is:

```text
RISING
STABLE
FALLING
UNKNOWN
```

Raw observation history remains preserved.

---

### Household Entities

HomHive distinguishes between a physical household entity and observations about that entity.

For example:

```text
HouseholdEntity
Monstera deliciosa
        ↓
Observation
plant_condition = 0.35
```

This allows one physical object to accumulate state over time.

State identity becomes entity-aware when an entity is known.

---

### Entity Resolution

The current backend separates object identification from physical entity resolution.

```text
Identification Candidate
        ↓
Compatibility Filtering
        ↓
Match Evidence
        ↓
Resolution
        ↓
MATCH / CREATE / UNCERTAIN
```

The current matching system is deterministic and operates on structured identification data.

Real visual identification has not yet been integrated.

---

### FastAPI and GraphQL

The backend currently uses:

- FastAPI
- Strawberry GraphQL

The API strategy is hybrid.

REST currently supports application health checks.

GraphQL currently supports entity queries and entity mutation behavior.

The API layer is separated from business logic through service and repository boundaries.

Entity persistence is currently in memory.

---

### Deterministic Forecasting

HomHive now has an initial forecasting baseline that estimates the rate at which a household condition is changing.

```text
Observation History
        ↓
Current Derived State
        ↓
Rate of Change
        ↓
Future State Estimate
```

The current implementation uses linear projection.

It is deliberately simple and deterministic so that later forecasting approaches can be evaluated against a known baseline.

---

### Threshold Prediction

Forecasts can be used to estimate when a condition may cross an actionable threshold.

Example:

```text
Dish load now:          0.62
Estimated growth:       +0.04/hour
Configured threshold:   0.75
                         ↓
Estimated threshold crossing
```

If the available trend does not support a crossing, HomHive does not invent one.

---

### Confidence-Aware Intervention

A predicted threshold crossing does not automatically become a task.

The current intervention layer can classify a prediction as:

```text
NONE
MONITOR
PLAN
ACT_NOW
```

This allows low-confidence or distant predictions to remain under observation rather than creating unnecessary work.

---

### Predictive Task Lifecycle

Actionable predictions can create predictive tasks.

As new observations arrive, the same logical task can change:

```text
PLAN
  ↓
Task created

ACT_NOW
  ↓
Task escalated

MONITOR
  ↓
Task dismissed

PLAN / ACT_NOW again
  ↓
Task reactivated
```

Repeated forecasts therefore do not need to create repeated copies of the same predictive task.

---

## Observation, State, Entity, and Task

These concepts are intentionally separate.

```text
ENTITY
What physical thing is this?

OBSERVATION
What did we observe about it?

STATE
What do we currently believe about its condition?

FORECAST
How might that condition change?

INTERVENTION
Does that prediction justify action?

TASK
What should be done?
```

Keeping these contracts separate is one of the main architectural principles of the project.

---

## Current Technology

### Backend

- Python
- FastAPI
- Strawberry GraphQL
- Pydantic
- pytest

### Planned Frontend

- Next.js
- mobile-first PWA

### Planned Persistence

- PostgreSQL / Supabase

### Planned AI and Research

- Nebius
- NVIDIA Nemotron
- Tavily

### Planned Evaluation and Observability

- LangSmith
- Toloka

### Other Available Tooling

- Tandem

External services listed above are planned or available to the project. They should not be interpreted as already integrated unless explicitly stated.

---

## Testing

Current backend test status:

```text
194 tests passing
```

The suite currently covers areas including:

- domain-model validation
- household-state updates
- observation history
- deterministic task discovery
- confidence handling
- task deduplication
- explainable discovery decisions
- task prioritization
- temporal state aggregation
- trend detection
- entity-aware state identity
- household entities
- entity identification contracts
- entity resolution
- GraphQL queries and mutations
- application-state isolation
- state forecasting
- threshold prediction
- forecast confidence
- intervention decisions
- predictive task discovery
- predictive task reconciliation
- predictive task lifecycle

The test count is a development checkpoint, not a production-readiness claim.

---

## Current Project Status

The backend currently reaches:

```text
Structured observations
        ↓
Household state
        ↓
Temporal aggregation
        ↓
Forecasting
        ↓
Threshold prediction
        ↓
Intervention decisions
        ↓
Predictive task lifecycle
```

The next major stages will connect this foundation to real household input and persistent application infrastructure.

---

## Not Implemented Yet

The following are part of the planned system but are not currently implemented:

- real photo analysis
- video ingestion
- multimodal vision integration
- Tavily-powered external research
- Nebius/Nemotron reasoning
- persistent database storage
- LangSmith tracing
- Toloka evaluation
- frontend integration
- calendar context
- email context
- quiet-hour constraints
- presence and availability reasoning
- learned forecasting
- autonomous robot execution

Keeping these separate from implemented functionality is intentional. The project is being developed incrementally, with each layer tested before the next major dependency is introduced.

---

## Planned Input Flow

The intended perception path is:

```text
Phone photo / short video
          ↓
Visual analysis
          ↓
Structured observations
          ↓
Household state
          ↓
Existing reasoning pipeline
```

When visual evidence is insufficient to identify an object, external research may later be used for enrichment.

For example:

```text
Appliance photo
      ↓
Visual clues
      ↓
Candidate manufacturer/model
      ↓
External verification
      ↓
Household entity
```

External research is intended to be conditional rather than performed for every observation.

---

## Design Principles

The current implementation follows several working principles:

- preserve raw observations
- keep state separate from evidence
- keep tasks separate from observations
- keep entity identity separate from entity condition
- use deterministic logic where deterministic logic is sufficient
- preserve uncertainty instead of forcing decisions
- keep prediction separate from intervention
- avoid creating tasks from weak predictions
- maintain stable task identity across repeated evaluations
- keep external AI providers outside core domain contracts
- make important decision paths testable and explainable

These principles may evolve as the project reaches real perception data and end-to-end evaluation.

---

## Documentation

Detailed project documentation is maintained under:

```text
docs/
├── architecture.md
├── current-state.md
├── decisions.md
├── evaluation.md
├── hackathon.md
└── product-spec.md
```

`architecture.md` describes how the implemented components fit together.

`current-state.md` records what has actually been built.

`decisions.md` records architectural decisions and the reasoning behind them.

`evaluation.md` contains the evaluation strategy.

`product-spec.md` defines the product direction.

---

## Development Status

HomHive is under active development.

The current implementation should be treated as an evolving prototype and engineering foundation rather than a production household automation system.

## License

MIT
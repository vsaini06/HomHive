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
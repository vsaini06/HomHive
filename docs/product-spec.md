# HomHive Product Specification

## Product definition

Build an intelligence layer that continuously understands household state, discovers tasks without requiring the human to create them, predicts when those tasks will become problematic, researches unfamiliar situations, and dynamically determines what humans or future robots should do next.

## Problem

Household work is usually managed reactively.

People often have to:

- notice a condition
- remember whether it is getting worse
- decide whether it matters now
- look up unfamiliar care or maintenance guidance
- compare it against other work
- decide when to act

Most task tools begin after a person has already identified the task.

HomHive begins earlier, at household state.

## Product questions

For each meaningful household condition, HomHive should eventually answer:

1. What needs to be done?
2. When does it need to be done?
3. Who or what should do it?

## MVP interaction

Target user flow:

```text
Open mobile web app
  |
  v
Capture or upload household photo / short video
  |
  v
HomHive extracts observations
  |
  v
Current household state is updated
  |
  v
Tasks are discovered or forecast
  |
  v
Unknown situations are researched when useful
  |
  v
Tasks are ranked and explained
  |
  v
User sees the current household plan
```

## Representative domains

### Dishes

Why it matters:

- fast-changing
- visually obvious
- good example of reactive and short-horizon work

### Laundry

Why it matters:

- capacity-like condition
- can often be delayed
- useful for intervention-window reasoning

### Plant care

Why it matters:

- uncertain visual state
- identity can materially affect guidance
- external knowledge may be required

### Lawn / outdoor

Why it matters:

- longer planning horizon
- seasonal or external context may matter
- useful example of selective research

## Product behavior

### State understanding

The user should not have to manually create every observation or task.

The product should transform evidence into structured household state.

### Task discovery

Obvious conditions should create work deterministically when possible.

LLMs should not be used simply because one is available.

### Forecasting

HomHive should distinguish:

- what is true now
- what is likely to happen
- whether that future condition justifies action

### Research

HomHive should research only when current state and household memory are insufficient.

Repeated stable questions should eventually reuse stored verified knowledge.

### Planning

Priority should be dynamic.

A task can remain the same task while its priority changes because of:

- urgency
- confidence
- deterioration
- deadline
- user context
- external evidence

### Executor abstraction

The plan should eventually be usable by:

- a person
- a household device
- a future robot

The MVP does not require building the robot.

## Non-goals for the MVP

- custom LLM training
- custom computer-vision training
- permanent household cameras
- custom hardware sensors
- continuous raw-video surveillance
- physical robot construction
- native iOS/Android apps if the PWA works
- support for every household domain
- autonomous safety-critical decisions

## Design principles

### Low friction

Phone media should be sufficient for the initial demo.

### Explainable decisions

The system should preserve why a task was created, deferred, monitored, or ranked.

### Conservative uncertainty

Uncertain evidence should not be silently upgraded into certainty.

### Selective intelligence

Use deterministic code when the rule is clear. Use research or model reasoning when the situation actually benefits from it.

### Stable contracts

Perception providers, search providers, and reasoning models should be replaceable without rewriting the household domain model.

## Success criteria

The MVP is successful when a user can provide household evidence and receive a coherent, explainable action plan that demonstrates:

- state understanding over time
- automatic task discovery
- forecasting
- selective research
- cross-domain prioritization
- replanning potential

The current repository has implemented the deterministic backend foundation for this target but not the complete end-to-end MVP.

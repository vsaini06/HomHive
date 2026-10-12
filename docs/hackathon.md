# HomHive Hackathon Notes

This file tracks submission-oriented constraints and integration goals separately from the core architecture.

## Product strategy

HomHive should demonstrate intelligence orchestration rather than a generic chatbot.

The product should show a credible path from household evidence to a dynamic action plan.

## Planned sponsor/runtime roles

### Nebius + NVIDIA Nemotron

Planned role:

- cross-domain reasoning
- constraint handling
- plan generation
- explanation
- future replanning

Current status:

```text
Not integrated in the current backend.
```

### Tavily

Planned role:

- selective research for unfamiliar or context-dependent situations
- entity verification/enrichment when identity matters
- grounded maintenance or care guidance

Current status:

```text
Not integrated in the current backend.
```

Tavily should not be called for every image or every routine task.

### LangSmith

Planned role:

- traces
- evaluation support
- debugging of model/tool workflows

Current status:

```text
Not integrated.
```

### Toloka

Potential role:

- evaluation / feedback workflows

Current status:

```text
Not integrated.
```

### Tandem

Potential role remains to be finalized.

## MVP proof points

The submission should eventually demonstrate:

- phone-based input
- normalized household state
- temporal memory
- automatic task discovery
- forecasting
- selective external research
- NVIDIA/Nebius runtime reasoning
- structured output
- mobile-first experience
- reproducible setup
- tests and evaluation

## Scope control

Do not spend the build window on:

- custom foundation-model training
- custom CV training
- permanent household hardware
- physical robotics
- dozens of domains
- safety-critical autonomous actions

The four representative domains are enough if the end-to-end behavior is convincing:

- dishes
- laundry
- plant care
- lawn / outdoor

## Current submission readiness

Backend deterministic foundation: strong

External runtime integrations: pending

Durable entity, observation, task, and media-metadata storage: implemented; automated application-wide orchestration and full audit history: pending

Image upload and private storage: implemented; single-image MiniCPM perception available; scene completeness and video processing pending

Frontend product flow: pending

End-to-end demo: pending

Evaluation: small real MiniCPM kitchen benchmark performed; representative coverage and calibration still pending

## Verified perception foundation

Nebius Token Factory MiniCPM vision inference is integrated into the authenticated media-to-observation API and has been exercised with actual stored images. Accepted output is stored as household-scoped evidence with unknown confidence preserved, rather than promoted directly into a household action. This is progress toward the demonstration, not proof that the required NVIDIA Nemotron runtime planning path or Tavily research integration is complete. Both remain separate implementation requirements for the intended hackathon submission.

## Current vision evidence and constraints

The local Day 15 regression suite reached 314 tests. Local `.env` support and a standalone vision-evaluation runner are available. The first five-image kitchen development benchmark exposed saturation in dish-load predictions; a revised rubric produced four completed cases and one failed case. Read-only multi-object scene inventory is implemented, but a successful live call detected only one drain in a multi-object kitchen. This is an unresolved quality limitation, not a demo-ready scene-understanding capability. NVIDIA Nemotron runtime integration and Tavily runtime research remain separate unfinished goals.

# HomHive Hackathon Notes

This file records submission-oriented product and integration status separately from the core architecture.

## Product strategy

HomHive should demonstrate household intelligence orchestration rather than a generic chatbot.

The strongest demo is a coherent loop:

```text
household image
-> structured evidence
-> remembered state
-> discovered + forecast work
-> selective research when knowledge is missing
-> deterministic feasibility constraints
-> NVIDIA Nemotron reasoning
-> plan
-> context change
-> replan
```

## Sponsor/runtime roles

### Nebius Token Factory

Verified roles:

- multimodal inference with `openbmb/MiniCPM-V-4_5`
- NVIDIA reasoning model access
- provider abstraction behind stable HomHive contracts

Live MiniCPM perception has been verified through the authenticated household media path.

### NVIDIA Nemotron

Verified role:

- cross-domain reasoning over ranked household tasks
- context-sensitive plan generation
- explanation of selected and deferred work

Live planning has been verified through Nebius using:

```text
nvidia/Nemotron-3_5-Lightning
```

HomHive validates returned task IDs and feasibility before accepting model output. Deterministic fallback remains available.

### Tavily

Verified role:

- selective research for unfamiliar or context-dependent situations
- normalized external evidence with source metadata
- household-scoped research API and durable cache support

Live Tavily search through HomHive has been verified. Tavily is intentionally not called for routine household facts such as ordinary dish or laundry load.

### Optional integrations

LangSmith, Toloka, and Tandem are not required for the verified core loop and are not currently integrated into the runtime claim.

## Verified submission proof points

- authenticated household image upload
- live Nebius multimodal perception
- explicit evidence review and user confirmation
- durable PostgreSQL household state
- reactive and predictive work generation
- deterministic ranking
- live Tavily research
- deterministic feasibility constraints
- live NVIDIA Nemotron planning
- dynamic replanning when available time changes
- mobile-first Next.js UI
- Dockerized FastAPI + Next.js + PostgreSQL runtime
- automated backend regression suite
- measured perception improvement on a human-labeled development set

## Measured perception result

On four human-reviewed kitchen scenes containing 59 reference entities:

```text
Joint prompt micro recall:       47.46%
Detection-first micro recall:    71.19%
Relative recall improvement:     50.0%

Joint micro-F1:                  58.33%
Detection-first micro-F1:        71.79%
```

These are development-set measurements, not general production accuracy claims.

## Demo scenario already verified

A browser run successfully executed:

```text
image upload
-> observation extraction
-> confirmation
-> intelligence refresh
-> two active household tasks
-> Nemotron plan at 20 available minutes
-> replan at 5 available minutes
```

At 20 minutes, one 15-minute task was selected and the other was deferred. At 5 minutes, both 15-minute tasks were deferred. The household state stayed the same while the executable plan changed with user context.

## Runtime verification

The Docker Compose stack has been built and started successfully with:

- PostgreSQL 17 healthy
- backend migrations applied at startup
- FastAPI `/health` returning HTTP 200
- Next.js production frontend returning HTTP 200
- persistent PostgreSQL and private-media volumes

This establishes reproducible local runtime packaging. It does not claim a public production deployment.

## Scope control

Do not weaken the core loop by chasing optional sponsor integrations or broad domain coverage.

Still outside the verified MVP:

- video/frame ingestion
- production authentication and household membership
- broad multi-domain perception benchmark
- reliable cross-image physical-entity identity
- background job orchestration
- full historical plan/audit log
- calendar/email/work-status integrations
- physical robot execution

## Submission framing

The submission should emphasize that HomHive separates:

```text
observation != state != task
importance != executability != fit
entity identity != condition
forecast != current state
```

The NVIDIA contribution is meaningful because Nemotron performs the cross-domain plan reasoning after HomHive has created structured household state and deterministic feasibility constraints. Tavily is meaningful because it supplies external evidence only where internal household knowledge is insufficient.

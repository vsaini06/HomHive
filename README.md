# HomHive

**The intelligence layer for the autonomous home.**

> **Implementation status (October 2026):** The source includes open-world independent visual review, autonomous task persistence, a room registry and a PostgreSQL-backed scan queue. Migration `0012_autonomous_room_category` and live end-to-end worker operation still require verification on the target installation. The original verification statistics below refer to earlier milestones and must not be mistaken for the latest system acceptance. See [Current state](docs/current-state.md).

HomHive turns household evidence into remembered state, discovered work, forecasts, selective external research, and a context-aware action plan. The goal is not another task list. The goal is a household intelligence layer that can understand what is changing, decide what matters, determine what is executable now, and preserve work that should wait.

## Product loop

```text
Phone photo / short video
        |
        v
Environmental perception
        |
        v
Structured observations
        |
        v
Household state + temporal history
        |
        +--------------------+
        |                    |
        v                    v
Reactive task discovery   Forecasting
        |                    |
        +----------+---------+
                   |
                   v
             Task ranking
                   |
                   v
      Selective Tavily research
                   |
                   v
 Deterministic feasibility constraints
                   |
                   v
 NVIDIA Nemotron cross-domain planning
                   |
                   v
      Human / future executor plan
```

HomHive keeps perception, state, forecasting, work discovery, executability, and planning as separate responsibilities. External AI providers sit behind adapters and never become the source of truth for durable household state.

## Verified current capabilities

- typed Pydantic domain models for observations, state, entities, forecasts, tasks, decisions, and plans
- confidence- and recency-aware household-state reconstruction from persisted observation history
- deterministic reactive task discovery and duplicate active-task prevention
- condition forecasting, threshold-crossing prediction, and predictive task lifecycle handling
- deterministic task scoring and ranking
- household-scoped PostgreSQL persistence through SQLAlchemy and Alembic
- authenticated private image upload and retrieval with media metadata stored separately from media bytes
- Nebius Token Factory multimodal perception using `openbmb/MiniCPM-V-4_5`
- explicit unknown model confidence using `None` / SQL `NULL`
- user confirmation that creates separate user evidence instead of rewriting AI evidence
- detection-first scene inventory with human-reviewed completeness scoring
- Tavily research with normalized source evidence and household-scoped research caching
- deterministic feasibility filtering for active time, passive time, at-home requirements, and quiet hours
- NVIDIA Nemotron planning through Nebius using `nvidia/Nemotron-3_5-Lightning`
- strict planner validation that rejects unknown task IDs and infeasible selections
- deterministic planning fallback when model output is unavailable or invalid
- mobile-first Next.js client for upload, evidence review, intelligence refresh, research-aware planning, and replanning
- Docker Compose runtime with Next.js, FastAPI, PostgreSQL 17, Alembic startup migrations, and persistent database/media volumes

## Verified end-to-end behavior

The browser flow has been exercised through the real API stack:

```text
private image upload
-> Nebius perception
-> structured household observation
-> explicit user confirmation when required
-> persisted household state
-> reactive + predictive work
-> ranking
-> NVIDIA Nemotron plan
-> context change
-> replanned result
```

A live kitchen run produced a `dish_load` observation, required user confirmation, refreshed persistent household intelligence, and generated a Nemotron plan. With 20 available active minutes, one 15-minute task was selected and the remaining work was deferred. With the same household state and only 5 available active minutes, no 15-minute task was selected and both tasks were preserved as deferred work.

This demonstrates a central HomHive invariant:

```text
importance != executability != fit
```

## Evaluation snapshot

Scene completeness is evaluated separately from schema validity and household-condition extraction.

A human-reviewed kitchen development set contains **59 reference entities across four scenes**.

| Pipeline | Matched | Predictions | Micro recall | Micro precision | Micro F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Joint object + condition prompt | 28 | 37 | 47.46% | 75.68% | 58.33% |
| Detection-first object discovery | 42 | 58 | 71.19% | 72.41% | 71.79% |

Detection-first inference improved scene-entity recall by **23.73 percentage points**, a **50.0% relative improvement**, while micro-F1 improved by **13.46 percentage points**. Precision decreased by 3.27 percentage points.

These are development-set measurements, not production accuracy claims. The scorer also has known vocabulary/granularity limitations, and one heavy-scene joint request required a retry after strict output validation rejected the first response.

## Verification status

- historical backend regression suite: **348 passed** (earlier milestone; latest reported Windows baseline: **496 passed**, not reproduced in this environment)
- frontend typecheck: passed
- frontend production build: passed
- npm audit during installation: 0 vulnerabilities
- live Nebius MiniCPM perception: verified
- live Tavily research: verified
- live NVIDIA Nemotron planning: verified
- live 20-minute to 5-minute context replan: verified
- Docker backend image build: verified
- Docker frontend image build: verified
- PostgreSQL container health: verified
- Alembic migration on container startup: verified
- FastAPI `/health`: HTTP 200
- Next.js production container: HTTP 200

## Architecture principles

1. Observation is not state.
2. State is not forecast.
3. Forecast is not action.
4. Task existence is not priority.
5. Importance is not executability.
6. Entity identity is not condition.
7. Unknown confidence remains unknown.
8. Raw evidence is preserved even when it cannot trigger action.
9. Deterministic rules handle obvious constraints before model reasoning.
10. AI output is parsed and validated before it can influence domain state or a plan.
11. Web content is evidence, not trusted authority.
12. Provider-specific objects stay outside stable domain contracts.

## Technology stack

**Backend:** Python, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, Strawberry GraphQL, PostgreSQL

**Frontend:** Next.js, React, TypeScript

**AI and research:** Nebius Token Factory, MiniCPM-V-4_5, NVIDIA Nemotron, Tavily

**Runtime:** Docker, Docker Compose, PostgreSQL 17

## Repository layout

```text
homhive/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── db/
│   │   ├── evaluation/
│   │   ├── media/
│   │   ├── models/
│   │   ├── planning/
│   │   ├── repositories/
│   │   ├── research/
│   │   ├── services/
│   │   └── vision/
│   ├── alembic/
│   ├── evaluation/
│   └── tests/
├── docs/
├── frontend/
├── docker-compose.yml
├── LICENSE
└── README.md
```

## Local backend setup

From `backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest -q
python -m uvicorn app.api.app:app --reload
```

Real credentials belong only in ignored local environment files or deployment-provided secrets.

## Local frontend setup

From `frontend`:

```powershell
npm install
$env:NEXT_PUBLIC_HOMHIVE_API_URL="http://127.0.0.1:8000"
npm run typecheck
npm run dev -- -H 127.0.0.1 -p 3001
```

The backend must allow the frontend origin through `HOMHIVE_ALLOWED_ORIGINS`.

## Docker Compose

Create a root `.env` from the example and provide local values for the database password, household token mapping, Nebius credentials/model, and Tavily key. Do not commit the real `.env`.

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

Verified local endpoints:

```text
Frontend: http://localhost:3001
Backend:  http://localhost:8000
Health:   http://localhost:8000/health
```

The Compose stack uses persistent volumes for PostgreSQL data and private media files.

## Main household API flow

```text
POST /households/{household_id}/media
POST /households/{household_id}/media/{media_id}/observations
POST /households/{household_id}/observations/{observation_id}/confirm
POST /households/{household_id}/intelligence/refresh
POST /households/{household_id}/research
POST /households/{household_id}/plan
```

The development bearer-token mapping is a local authentication mechanism, not a production identity system.

## Current limitations

- video ingestion and frame sampling are not yet implemented
- scene completeness has improved but is still evaluated on a small kitchen development set
- persistent cross-image physical-entity identity is not production-ready
- reactive and predictive tasks can still represent the same underlying household work with different task keys
- historical plan/audit events are not fully persisted
- the full observation-to-task workflow is not transactionally atomic under concurrent processing
- calendar, email, richer presence, and work-status integrations are not implemented
- background execution for long-running provider calls is not implemented
- production user accounts, household membership, and production-grade media authorization are not implemented
- local Docker runtime is verified, but public production deployment is not claimed

## Documentation

- [`docs/architecture.md`](docs/architecture.md) - system boundaries and data flow
- [`docs/current-state.md`](docs/current-state.md) - verified implementation state
- [`docs/evaluation.md`](docs/evaluation.md) - measured evaluation and testing strategy
- [`docs/decisions.md`](docs/decisions.md) - architecture decisions and open design questions
- [`docs/hackathon.md`](docs/hackathon.md) - submission-oriented integration status
- [`docs/product-spec.md`](docs/product-spec.md) - product scope and behavior

## License

MIT

## Interface and verification integration (October 2026)

The web client separates **AI-corroborated**, **human-confirmed**, and **unverified** observations. Agreement between independent vision reviewers does not create a synthetic numeric confidence or a human confirmation. Reusing a processed media ID returns the persisted observation rather than initiating another analysis. The household intelligence refresh advances overdue completion checks using existing trusted evidence; it never treats the user's Done action as proof that a condition was resolved.

Local setup uses both root and backend `.env` files. Keep secrets out of version control. Existing process variables may override file values, so verify which terminal starts Uvicorn after rotating a provider credential. The current task estimator still uses deterministic category defaults; evidence-grounded research estimates remain planned work. See `docs/current-state.md` for limitations and `frontend/README.md` for the interface.

## Autonomous consumer workflow

With the autonomous flags and all three provider credentials configured, a saved household photograph enters a durable queue. The worker independently corroborates a scene with Nebius, OpenAI and Claude, reviews evidence-grounded proposed actions and stores justified tasks in PostgreSQL. The household's first independently verified image can establish its first physical-room reference automatically; later images require trustworthy room continuity. User actions and actual creation/update timestamps are persisted. A 30-minute snooze is in-app only; reporting Done is not independent proof of completion.

The queue worker must be running separately and reads `backend/.env` before checking feature flags. Configuration errors stop startup rather than creating unreachable work. Run `python scripts/live_smoke.py --image <path>` from `backend` after starting FastAPI and the worker to verify the real API-to-worker-to-task path in your own network-enabled environment. Use a dedicated test account and avoid production secrets.

See `docs/implementation-audit.md` for verification status, security constraints, remaining gaps and installation instructions.

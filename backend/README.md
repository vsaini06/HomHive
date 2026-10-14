# HomHive backend

The backend is a FastAPI application built around explicit domain, service, repository, provider, and persistence boundaries.

## Local setup

From `backend` on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest -q
python -m uvicorn app.api.app:app --reload
```

Explicit process environment variables override values loaded from `backend/.env`. Real secrets must not be committed or printed.

The current Alembic head is `0006_research_cache`.

## Verified regression baseline

```text
348 passed
```

The suite covers domain rules, persistence, household isolation, media authorization, vision validation, scene completeness scoring, evidence confirmation, intelligence refresh, Tavily research/cache behavior, planning feasibility, and planning APIs.

## Image and observation path

Authenticated JPEG, PNG, and WebP uploads are stored privately. PostgreSQL stores household-scoped media metadata separately from file bytes.

```text
stored household image
-> Nebius MiniCPM-V-4_5
-> validated candidate observation
-> explicit review when confidence is unknown
-> household-scoped ObservationStorage
-> PostgreSQL
```

The vision provider does not invent a calibrated confidence value. Unknown confidence is preserved as `None` / SQL `NULL`. Explicit confirmation creates separate user evidence rather than rewriting the original AI observation.

## Scene inventory and completeness

`evaluation.run_scene` supports joint and detection-only scene inventory. `evaluation.run_scene_completeness` scores predictions against human-reviewed reference inventories.

Across four kitchen scenes with 59 reference entities:

```text
Joint micro recall:       47.46%
Joint micro F1:           58.33%
Detection micro recall:   71.19%
Detection micro F1:       71.79%
Relative recall gain:     50.0%
```

These are development-set measurements. Detection-only inference is intentionally separated from condition assessment so object discovery can be evaluated independently.

## Intelligence and planning

`POST /households/{household_id}/intelligence/refresh` reconstructs household state from durable observations, discovers reactive work, calculates forecasts, reconciles predictive work, and ranks active tasks.

`POST /households/{household_id}/plan` applies deterministic feasibility constraints before accepting an executable plan. Active time, passive time, at-home requirements, quiet hours, and task limits are handled separately from task importance.

When `NEBIUS_REASONING_MODEL` is configured with an NVIDIA Nemotron model, the planner can use Nebius reasoning. Model output is strictly validated for known task IDs and feasibility, with deterministic fallback if provider output is unavailable or invalid.

A live run with `nvidia/Nemotron-3_5-Lightning` was verified. The same persisted task set produced one selected task with 20 available active minutes and no selected tasks with 5 available active minutes.

## Research

When `TAVILY_API_KEY` is configured, `POST /households/{household_id}/research` performs household-authorized Tavily search. Results are normalized into source evidence before they can be used by planning. Research records can be cached in PostgreSQL through the `research_cache` table.

Live Tavily runtime search has been verified. Cache behavior is covered by automated tests; a separate live cache-hit reuse claim is not required for the current runtime evidence.

## Docker runtime

The backend image starts by applying Alembic migrations and then serving FastAPI on port 8000. The Docker Compose stack has been verified with PostgreSQL 17 reporting healthy and `/health` returning HTTP 200.

From the repository root:

```powershell
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

## Important boundaries

- observations are evidence, not tasks
- derived state is reconstructable from persisted observations
- forecasts do not directly imply actions
- task identity is separate from ranking
- provider output is never persisted or executed without parsing and validation
- web research is untrusted evidence
- development household bearer tokens are not production authentication

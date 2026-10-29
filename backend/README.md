# HomHive backend

FastAPI, PostgreSQL persistence, multimodal evidence review, and the durable autonomous worker.

## Local setup

From `backend/` in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m pytest -q
python -m uvicorn app.api.app:app --reload --host 127.0.0.1 --port 8000
```

Keep all provider credentials, account secrets, and household bearer tokens in `backend/.env` or private process environment variables. Inherited environment variables take precedence over local `.env` values.

The autonomous scan route requires `HOMHIVE_ENABLE_OPEN_WORLD_PREVIEW`, `HOMHIVE_ENABLE_AUTONOMOUS_SCAN`, and `HOMHIVE_ENABLE_AUTONOMOUS_QUEUE` set to `true`. It also requires a valid PostgreSQL `DATABASE_URL`, private media root, household-token mapping, `NEBIUS_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and supported `HOMHIVE_OPENAI_REVIEW_MODEL` / `HOMHIVE_ANTHROPIC_REVIEW_MODEL` values. Set `HOMHIVE_ACCURACY_FIRST=true` where the accuracy-first path is desired.

Run the worker in its own terminal with the same configuration:

```powershell
$env:HOMHIVE_ACCURACY_FIRST = 'true'
$env:HOMHIVE_AUTO_ORCHESTRATION = 'true'
python -m app.vision.autonomous_worker_cli
```

The worker handles scans, optional Tavily research, and Nemotron advice following supported state changes. For automatic advice use an available NVIDIA model such as `nvidia/nemotron-3-super-120b-a12b` through Nebius Token Factory, configured with `NEBIUS_ADVICE_MODEL` if necessary.

## Safety and evidence

Visual claims undergo independent review before they can justify autonomous tasks. Evidence is separate from task state and user-reported completion; no synthetic confidence is assigned when calibration is unavailable. Research text and model output are validated before use. Inaccessible providers should not result in invented observations.

## Verification

Run `python -m pytest -q` in the activated backend environment. Run `python -m alembic current` to confirm the local database is migrated. The migration files include `0017_autonomous_object_identity` and must not be deleted or skipped.

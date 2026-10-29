# Operations and demo

## Existing Windows setup

Use the already tested local PostgreSQL database for the hackathon video. Do not switch runtimes immediately before submission unless the original environment is unusable.

Start backend from `backend/` after activating `.venv`:

```powershell
python -m alembic current
python -m uvicorn app.api.app:app --reload --host 127.0.0.1 --port 8000
```

Start the autonomous worker in another activated backend terminal:

```powershell
$env:HOMHIVE_ACCURACY_FIRST = 'true'
$env:HOMHIVE_AUTO_ORCHESTRATION = 'true'
python -m app.vision.autonomous_worker_cli
```

Start the UI from `frontend/`:

```powershell
npm run dev -- -p 3001
```

Local URLs: `http://localhost:3001` and `http://127.0.0.1:8000/health`. Confirm allowed CORS origins, database, credentials, and active feature flags before a live scan.

## Suggested demo walkthrough

1. Introduce HomHive as an evidence-to-decision layer, not a task-list chatbot.
2. Show a known baseline photo from the curated gallery and its recognized room context.
3. Show a verified changed image, task creation, and grounded visual evidence.
4. Show a later image of the same verified space and explain *visible* progress without claiming physical chore completion.
5. Open Tasks, Spaces, and Objects to show persisted context.
6. Show the Automation screen, deterministic feasibility, and a live or already verified Nemotron decision.
7. Show Tavily citations only when a completed result is actually attached and displayed.
8. Close with future camera/robot orchestration explicitly labeled as a product vision.

Use a repeatable sequence with confirmed behavior; do not depend on a cold multi-provider scan completing during a three-minute video.

## Validation

```powershell
cd backend
python -m pytest -q
python -m alembic current
```

```powershell
cd frontend
npm run typecheck
npm run build
```

Check the health endpoint and the worker log. A Tavily HTTP 200 indicates provider connectivity, not necessarily a rendered object-specific source. For tasks, an unknown duration is valid when evidence is insufficient.

## Optional Docker demonstration

`compose.demo.yml` defines a separate, local-only PostgreSQL and media deployment. It uses local environment configuration and does not migrate data from a running Windows database.

```powershell
Copy-Item deployment.env.example .env
Copy-Item backend/.env.example backend/.env
# Supply private values in both files.
docker compose -f compose.demo.yml config --quiet
docker compose -f compose.demo.yml up --build
```

Do not publish an unmodified demo deployment to the internet. User security, rate limiting, secret rotation, backup policy, and operational monitoring require additional work.

## Source hygiene

Never commit `.env` files, secrets, private household media, `.venv`, `node_modules`, `.next`, backup files, local databases, or log output. Leave tracked migrations, automated tests, and gallery assets intact.

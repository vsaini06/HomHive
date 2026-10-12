# HomHive backend

## Local setup

From `backend` on Windows PowerShell, activate `.venv` and install `requirements.txt`. Copy `.env.example` to `.env` and supply your local database connection, media root, household token mapping, and Nebius key. Do not commit `.env` or print secrets. Shared configuration loading supports FastAPI, Alembic, and standalone vision scripts. Explicit environment variables take precedence over `.env`.

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic current
python -m pytest -q
python -m uvicorn app.api.app:app --host 127.0.0.1 --port 8001
```

The last locally reported full regression result was **314 passed**. The PostgreSQL database migration head was `0005_unknown_confidence`. Port 8001 is illustrative and must be available.

## Vision paths

- Authenticated media upload and retrieval store files privately and metadata in PostgreSQL.
- Authorized MiniCPM condition extraction can persist evidence-backed observations with `confidence: null`; this does not itself create tasks.
- `python -m evaluation.run_vision --manifest evaluation/cases.json --images evaluation/images --output evaluation/report.json` runs the independent condition benchmark. Errors are recorded per case; completion rate must accompany accuracy metrics.
- `python -m evaluation.run_scene --image evaluation/images/kitchen_light_01_small.jpg --location kitchen --output evaluation/scene_light.json` runs the **experimental read-only** scene inventory when that local test image exists. It does not save entities, observations, or tasks. The call consumes Nebius inference credits.

The scene-inventory schema distinguishes entity presence from conditions, carries visible evidence, and records unsupported condition claims for review. A live test completed but identified just one drain despite multiple visible objects. Do not interpret successful schema validation as scene completeness or condition accuracy.

See `docs/architecture.md`, `docs/scene-inventory.md`, and `docs/evaluation.md` in the repository root.

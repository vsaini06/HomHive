# HomHive

**The intelligence layer for the autonomous home.**

HomHive turns household photographs into verified observations, persistent room and object context, evidence-based tasks, and context-aware plans. Rather than requiring someone to enter every chore, HomHive discovers work from changes in the home and helps decide what is worth doing next.

## What HomHive does

1. **Observe:** Upload a household photo, or select an example from the demo library.
2. **Verify:** Nebius-powered vision proposes visible evidence. Independent image reviews using OpenAI and Anthropic check claims before they influence household decisions.
3. **Remember:** Store scan history, distinguish physical rooms, and retain object identity and task state in PostgreSQL.
4. **Discover:** Create and update justified household tasks; avoid duplicates and preserve uncertainty when evidence is insufficient.
5. **Research:** Use Tavily selectively for unfamiliar objects, care questions, and grounded effort research.
6. **Coordinate:** Apply availability, quiet-hours, duration, presence, and other deterministic restrictions before requesting a plan from NVIDIA Nemotron through Nebius Token Factory.
7. **Reassess:** Compare later evidence with previous observations and report supported visible progress, without treating disappearance from a photo as proof that work was physically completed.

```text
Photograph -> Nebius vision -> Independent review -> Verified evidence
     -> Persistent rooms / objects / task history
     -> Task discovery + progress evaluation
     -> Selective Tavily research
     -> Feasibility checks -> NVIDIA Nemotron advice
     -> Household decision interface
```

## Demo highlights

- **Space continuity:** A recognized room category is not treated as proof that two images show the same physical room.
- **Object-first views:** Close-up objects can have an independent identity without a confirmed room assignment.
- **Evidence-grounded progress:** Original and changed images can update task progress when a valid relationship has been established.
- **Autonomous coordination:** A background worker can trigger research and replanning after meaningful completed scans.
- **Human control:** Users review recommendations, task history, and reasons; HomHive does not control real appliances or robots.

The product also includes a curated demonstration image gallery. Its descriptive filenames are catalog metadata, **not** model predictions or verified object/species labels.

## Stack

| Layer | Technology |
| --- | --- |
| Web application | Next.js 16, React, TypeScript |
| API and background worker | FastAPI, Python, Pydantic |
| Persistence | PostgreSQL, SQLAlchemy 2, Alembic |
| Multimodal perception | Nebius Token Factory, with independent OpenAI and Anthropic review |
| Decision advice | NVIDIA Nemotron via Nebius Token Factory |
| External research | Tavily |
| Local deployment | PowerShell or Docker Compose |

## Run locally

Requirements: Python 3.12+, Node.js, PostgreSQL, and credentials for the AI services used by the chosen workflow. The application's autonomous mode requires separately configured providers and a worker process.

**Backend**, from `backend/` in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Configure backend/.env privately, then create/update the PostgreSQL database.
python -m alembic upgrade head
python -m uvicorn app.api.app:app --reload --host 127.0.0.1 --port 8000
```

**Worker**, in a separate activated backend terminal:

```powershell
$env:HOMHIVE_ACCURACY_FIRST = 'true'
$env:HOMHIVE_AUTO_ORCHESTRATION = 'true'
python -m app.vision.autonomous_worker_cli
```

These flags control accuracy-first review and automatic post-scan coordination. The backend and worker must also have the autonomous feature flags, household/media settings, and the appropriate API keys configured; see [backend setup](backend/README.md). The worker does not run merely because the API is running.

**Frontend**, from `frontend/` in another terminal:

```powershell
npm ci
$env:NEXT_PUBLIC_HOMHIVE_API_URL = 'http://127.0.0.1:8000'
npm run dev -- -p 3001
```

Open `http://localhost:3001`. Backend health check: `http://127.0.0.1:8000/health`. Keep account and provider credentials out of the browser bundle and Git.

Alternatively, `compose.demo.yml` defines an **optional localhost-only** PostgreSQL/API/worker/web stack. It creates separate database volumes and does not import the existing Windows demo database. See [operations](docs/operations.md).

## Tests

```powershell
cd backend
python -m pytest -q
```

```powershell
cd frontend
npm run typecheck
npm run build
```

The latest Windows working-copy report before this documentation cleanup was **684 passing backend tests**, plus successful frontend typecheck and build. Run the checks in your own checkout after applying cleanup changes. Model inference and live-provider credentials require separate end-to-end verification.

A small development evaluation compared joint and detection-first scene inventory on four labeled kitchen scenes with 59 reference entities. Detection-first micro recall increased from **47.46% to 71.19%**; this is not a production accuracy claim. [Evaluation details](docs/evaluation.md).

## Known limitations

- Independent plant species identification and object-specific Tavily source display are **not yet verified end-to-end**. A successful Tavily API response does not guarantee an object card receives sources.
- Room and object matching preserve uncertainty, and ambiguous images can need confirmation.
- Task durations and completion percentages can be unknown or approximate. Visual change is not independent proof a physical task was performed.
- Video ingestion, continuous camera sensing, autonomous robot/appliance control, and direct calendar management are future directions, not implemented demo capabilities.
- Local development authentication and Docker settings are not a production security deployment.

## Documentation

- [Architecture](docs/architecture.md)
- [Product behavior](docs/product-spec.md)
- [Local operation and demo walkthrough](docs/operations.md)
- [Evaluation](docs/evaluation.md)
- [Demo image library](docs/demo-library.md)
- [Hackathon submission notes](docs/hackathon.md)

## License

MIT. See [LICENSE](LICENSE).

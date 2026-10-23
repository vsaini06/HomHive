# HomHive frontend

The frontend is a mobile-first Next.js interface for the household intelligence API.

## Product flow

```text
household connection
-> private image upload
-> vision extraction
-> evidence review / confirmation
-> household intelligence refresh
-> optional research question
-> context-aware plan
-> replan when constraints change
```

The development bearer token is entered in the interface and remains in the current page state. This is not production authentication.

## Local setup

```powershell
npm install
$env:NEXT_PUBLIC_HOMHIVE_API_URL="http://127.0.0.1:8000"
npm run typecheck
npm run dev -- -H 127.0.0.1 -p 3001
```

The backend must include the frontend origin in `HOMHIVE_ALLOWED_ORIGINS`.

## Production build

```powershell
npm run typecheck
npm run build
```

Both commands have been verified successfully for the current client.

## Docker

The Compose stack publishes the production frontend at:

```text
http://localhost:3001
```

The production container has been verified to return HTTP 200 while connected to the Dockerized FastAPI/PostgreSQL stack.

## Current UI behavior

The interface exposes:

- API URL, household ID, and bearer token connection fields
- room/location selection and private image upload
- extracted household evidence and explicit confirmation
- current intelligence and ranked work
- available active minutes, at-home state, and quiet-hours context
- optional research question
- plan generation and deferred-work explanations

A live browser scenario verified that changing only available active time from 20 minutes to 5 minutes changed the plan while preserving the underlying household work.

## Current interface

HomHive provides Home, Spaces, Tasks, and Activity views, private photo upload, an evidence timeline, household connection settings, and action controls (Accept, Later, Dismiss, Done). The responsive design uses a shared typographic system, improved focus treatment, reduced-motion support, and semantic status announcements. The UI now labels explicitly corroborated AI observations distinctly from human-confirmed observations. An unknown room remains unknown rather than being inferred from a task description.

Use `npm ci`, `npm run typecheck`, and `npm run build` inside `frontend/` to validate dependencies, TypeScript and the production bundle. Configure `NEXT_PUBLIC_HOMHIVE_API_URL` where needed. Authentication tokens are entered into the client session; do not put household tokens in `NEXT_PUBLIC_` variables or commits.

**Not yet proven:** comprehensive accessibility audits, cross-browser/mobile device testing, and production readiness. A polished shell does not itself establish complete product workflows.

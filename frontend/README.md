# HomHive frontend

Next.js 16 and React interface for image-based household intelligence, space continuity, object cards, task evidence, and the coordination planner.

## Local development

From `frontend/`:

```powershell
npm ci
$env:NEXT_PUBLIC_HOMHIVE_API_URL = 'http://127.0.0.1:8000'
npm run typecheck
npm run dev -- -p 3001
```

The backend's `HOMHIVE_ALLOWED_ORIGINS` must include `http://localhost:3001` if that is the browser origin. The backend and autonomous worker need to be running to process new photos.

## Production build

```powershell
npm run typecheck
npm run build
npm run start -- -p 3001
```

The demo library is stored under `public/demo-library/`. Its titles and filenames describe demonstration assets, not verified AI findings. The Objects page deliberately leaves uncertain species identities and physical locations unconfirmed; absence of research sources is displayed rather than replaced with fabricated references.

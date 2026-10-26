# HomHive frontend

Next.js consumer client for household uploads and intelligent task review.

## Local development

```powershell
cd 'C:\AI Projects\homhive\frontend'
$env:NEXT_PUBLIC_HOMHIVE_API_URL = 'http://127.0.0.1:8000'
npm ci
npm run typecheck
npm run build
npm run dev -- -p 3001 -H 0.0.0.0
```

The backend's `HOMHIVE_ALLOWED_ORIGINS` must include the actual frontend origin. For local-device access also configure the LAN API host, firewall and Next.js `allowedDevOrigins` deliberately. Do not use permissive CORS or expose development credentials to the internet.

## Scan behavior

Image uploads are saved and are expected to enqueue durable open-world processing. The client observes background job status instead of automatically invoking the old fixed-condition `/observations` analysis endpoint. An independently corroborated first image automatically establishes the household's initial physical-room reference. Subsequent images must pass same-room comparison; uncertain new rooms can be confirmed from the consumer interface. An `unverified_room` status is not a completed scan. No task is created solely to populate an empty screen.

New autonomous suggestions retain image-grounded explanations and a recognized room category when verified. The registered physical-room identity is separate. Where no justified estimate exists the UI shows unknown duration rather than a default number.

Legacy observations and tasks remain accessible in the existing backend for compatibility; the autonomous experience suppresses new fixed-template recommendations when the autonomous queue is active. Historical legacy records are not automatically deleted.

## Product completeness

Autonomous task decisions are persisted, including in-app snoozing. Full household membership/invitations, OS/email notifications, integrated open-world manufacturer research, and external sensor integrations remain unfinished or unverified. Do not present mock controls as working features.

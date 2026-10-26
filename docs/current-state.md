# HomHive Current State

## Runtime architecture

HomHive stores household-scoped media, observations, tasks and evidence in PostgreSQL and a private media store. The backend exposes authenticated upload, history and account interfaces. A separate, opt-in autonomous queue can process new uploads in a worker. The current schema head is `0012_autonomous_room_category`; a running local database must be checked independently with `python -m alembic current`.

The autonomous path uses open-vocabulary image analysis rather than fixed household chore categories. When enabled and configured, Nebius performs primary scene extraction, Claude reviews visual claims against the original image, and OpenAI independently reviews them as well. Only claims supported by both independent reviews enter the open-world planner. The planner proposes an action only from those claims, and a separate image-aware action reviewer decides if the action is justified. Verified room *category* is separate from persistent physical-room identity. When a household has no enrolled rooms, an independently corroborated first photograph with a supported room category establishes its first physical-room reference automatically. Later photographs require independently reviewed continuity; uncertain matches are held.

Action records preserve a verified scene category, an excerpt of the image-grounded evidence, task-specific completion criteria and an effort range only when one is justified. An unknown duration remains `null`, never an invented default. Open-world actions use database-backed deduplication and fresh-image completion verification.

## Autonomous activation

The backend requires the appropriate API credentials and selected model names, plus the following flags in its local private configuration:

```env
HOMHIVE_ENABLE_OPEN_WORLD_PREVIEW=true
HOMHIVE_ENABLE_AUTONOMOUS_SCAN=true
HOMHIVE_ENABLE_AUTONOMOUS_QUEUE=true
HOMHIVE_OPENAI_REVIEW_MODEL=<supported-image-review-model>
HOMHIVE_ANTHROPIC_REVIEW_MODEL=<supported-Claude-model>
HOMHIVE_NEBIUS_VISION_MODEL=openbmb/MiniCPM-V-4_5
```

Provide `NEBIUS_API_KEY`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY` privately, not in Git. The supported image model and the service's live output contract must be checked in the target environment. A worker is started separately via `python -m app.vision.autonomous_worker_cli`; merely starting FastAPI does not execute durable scans.

If the queue is enabled, `refresh_household_intelligence` retains existing legacy tasks and observation history but stops creating **new** fixed-template reactive/predictive chores. This prevents a clothing pile from becoming a 45-minute laundry recommendation due to a legacy mapping. New image uploads enqueue for independent open-world processing. If queueing is not available the frontend should report that condition rather than silently switch to the preset analysis path.

## Known product limitations

- The first independently verified photograph can automatically establish the household's first room reference. Further unrecognized rooms may require a consumer's confirmation to avoid merging physically distinct rooms.
- Existing previously saved legacy tasks and notifications are preserved; hiding legacy suggestions in autonomous mode is not database deletion. Existing misinformation should be individually reviewed/dismissed, not silently rewritten.
- Accept, Decline, Snooze, and Done actions are database-backed. Snooze records a due time and hides the task in the browser until it becomes due; it does not deliver OS push or email. Done records user-reported completion, not visual proof.
- This source package does not demonstrate live Nebius/OpenAI/Claude inference, precise work duration calibration, real manufacturer-research attribution or calendar OAuth.
- Production worker concurrency, browser/mobile push, background camera access and full deployment operations require separately verified environment setup.

## Verification

The runnable test subset and current verification results are documented in `implementation-audit.md`. Three GraphQL-related modules cannot collect without the Strawberry dependency in this sandbox. TypeScript parsing is verified, but production typechecking/building and live provider/database operations require a network-enabled environment. These checks do not establish successful live inference or deployment.

The source package uses file preimage and payload SHA-256 validation. Apply it only against a compatible checkout and validate on Windows before treating it as usable.


## Current consumer task workflow

When the autonomous queue and scan worker are enabled, new photo uploads use the durable open-world scan workflow. Tasks shown in the main consumer task view come from `autonomous_tasks`, not the legacy fixed-category suggestion list. Task cards show persisted creation/update times, independently reviewed evidence, estimated effort only when grounded, and server-backed decisions. The historical fixed-category tasks remain in the database but are not silently deleted.

The first independently corroborated photograph of a household now automatically establishes an initial physical room reference when the room category is supported. Further previously unseen physical spaces may require a user decision after matching fails. A room category such as *walk-in closet* is not proof that two photographs show the same exact closet. The app must hold uncertain room continuity rather than assign a random room.

The autonomous task decision endpoint accepts `accept`, `decline`, `remind`, and `done`. A reminder request records a 30-minute due timestamp; the browser suppresses that task until its due time on a later refresh. Actual out-of-app notification delivery still requires a scheduler and notifier. Reporting Done records a claim only and remains subject to independently reviewed fresh evidence. Do not claim that new task notifications, reminder delivery, calendar OAuth, or live three-model calls have been tested without corresponding runtime evidence.

For a local three-model run, `HOMHIVE_ENABLE_AUTONOMOUS_QUEUE=true` and `HOMHIVE_ENABLE_AUTONOMOUS_SCAN=true` must be set, the database must be at `0012_autonomous_room_category`, and one `python -m app.vision.autonomous_worker_cli` process must be active with permitted provider credentials. Existing household media and task state should be preserved; repeat image uploads must not be used as a substitute for diagnosing queue status.

# Autonomous household coordination

HomHive processes an authorized household photograph using multimodal perception,
independent evidence review, open-world action planning, and independent necessity
review. Only independently approved, evidence-cited actions are persisted. A
corroborated observation does not automatically justify an action.

## Task discovery and recommendation

Approved ordinary actions become suggestions without an acceptance step. Tasks
requiring the user's explicit consent for safety or professional involvement remain
in a confirmation-required state. Task suggestions, verified progress changes, and
completion become durable, household-scoped in-app notifications. Notifications are
visible when the user next opens HomHive; they do not imply external push delivery
when the browser is closed.

The duration researcher searches external published material and accepts estimates
only when two independent domains provide compatible explicit duration statements.
An estimate is labeled approximate with citations and may remain unknown. The
planner does not substitute a guessed duration if research is inconclusive.

A household may set preferred weekdays, a local time window, and a time zone.
HomHive suggests a time only when the researched upper duration bound fits within
that preference. The preference does not constitute access to a calendar or proof
that the user is available then. If a calendar connector is added later, conflict
and consent checks belong at that separate integration boundary.

## Follow-up evidence and progress

New photographs are matched to a physical room through independent image-pair
verification; common room categories do not prove continuity. The same photograph
that created the task cannot verify its resolution.

For every active task in a verified room, independent follow-up review compares
fresh corroborated evidence with the original task's completion criterion and
records the actual reviewer verdict. When sufficiently visible, it may provide a
rough percentage, such as 20% or 60%, plus concrete remaining work. This is a
subjective evidence-supported progress *estimate*, not a measured area fraction,
work-time fraction, or guarantee. Progress can regress if a later photograph shows
that the condition worsened. A photo missing the relevant area leaves the last
supported progress unchanged, rather than resetting it to zero or calling it done.

Only a new photograph supporting the full verification criteria marks the task
completed (100%). The user can optionally report that work was done, but that
report is not itself independently verified completion. Verification and progress
events are idempotent for each (household, task, media) pair.

## Failure and operational boundaries

- An uncertain or unmatched room is held rather than linked to another room.
- Review refusal or insufficient evidence can legitimately create no task.
- Provider timeouts, invalid outputs, and exhausted rate limits are surfaced as
  explanatory failure states, without disclosing credentials or raw model data.
- In-app notifications are not push notifications, text messages, or scheduled
  delivery when the frontend is closed.
- Background scan processing requires the configured worker and live providers.
- Estimated completion progress requires real follow-up images and has not been
  established as a calibrated numeric prediction.

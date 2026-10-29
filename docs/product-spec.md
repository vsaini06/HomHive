# Product behavior

## Objective

HomHive interprets household evidence over time, identifies changes worth acting on, researches unfamiliar problems, and produces plans that respect a household's current constraints.

## Current user journey

1. Sign in to a configured household and upload an image or select a demonstration sample.
2. Track the scan's background status, evidence, and any explicit uncertainty.
3. Review discovered tasks and observations assigned to a verified physical space or a persistent object.
4. Compare later evidence for the same confirmed room or object and inspect supported changes.
5. Use the Automation screen to choose availability, preferred work times, and other constraints.
6. Review prioritized tasks, research where available, and Nemotron advice for currently eligible work.
7. Confirm, defer, or report completion through the supported task workflow.

## Product invariants

- An observation is not a task.
- Similar room labels are not proof of one room.
- A catalog title is not an AI identification.
- Missing research is displayed as missing; it does not become a fabricated diagnosis or source.
- User-reported completion does not establish verified physical completion.
- A photo with a missing object does not prove the underlying chore was completed.
- Priority is separate from feasibility, and unavailable time estimates remain unknown.
- Background provider failure must not silently create unsupported work.

## Current scope and next steps

**In scope:** uploaded photographs, independently reviewed scene evidence, stored household history, room continuity, persistent object records, task discovery and progress, optional Tavily research, deterministic feasibility, and Nemotron advice.

**Not yet demonstrated end-to-end:** reliable independent plant species identification on the object card; automatic display of object-linked Tavily citations in every relevant scan.

**Future direction:** ongoing camera/sensor perception, appliance and robot dispatch, learning individual household preferences, and richer provider integrations. These are product goals rather than current execution capabilities.

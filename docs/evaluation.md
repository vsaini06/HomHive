# HomHive Evaluation

## Purpose

HomHive is evaluated as a household decision system, not only as a collection of endpoints.

Evaluation is separated into:

1. deterministic regression testing
2. perception and scene-completeness measurement
3. research-provider behavior
4. planning and constraint behavior
5. end-to-end product verification

## Automated regression baseline

The current complete backend suite passes:

```text
348 tests
```

Coverage includes:

- observation validation and household state behavior
- confidence/recency aggregation and trend detection
- reactive task discovery and duplicate prevention
- task ranking and lifecycle behavior
- entity models, matching, resolution, repositories, and GraphQL boundaries
- condition forecasting, threshold crossing, action decisions, and predictive task lifecycle
- SQLAlchemy and in-memory repository contracts
- household-scoped observation/task/media isolation
- authenticated media validation and retrieval
- nullable unknown-confidence behavior
- vision parsing and validation
- scene-inventory parsing and completeness scoring
- explicit observation review/confirmation
- household intelligence refresh
- Tavily provider, API, and cache behavior
- planning feasibility and planning APIs

Test count is a regression measure, not a claim of perception or planning quality.

## Perception evaluation principles

Schema-valid output is not the same as correct or complete perception.

HomHive therefore measures separate properties:

- whether a provider response is structurally valid
- whether visible entities are discovered
- whether unsupported condition claims are rejected
- whether household-condition extraction is calibrated
- whether provider failures are surfaced rather than converted into fabricated results

## Scene-completeness development set

The current human-reviewed kitchen set contains four scenes and 59 reference entities.

| Scene | References | Joint matched / predicted | Joint recall | Joint precision | Detection matched / predicted | Detection recall | Detection precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Light | 12 | 1 / 1 | 8.33% | 100.00% | 9 / 11 | 75.00% | 81.82% |
| Clean | 11 | 9 / 11 | 81.82% | 81.82% | 8 / 11 | 72.73% | 72.73% |
| Moderate | 17 | 9 / 12 | 52.94% | 75.00% | 11 / 15 | 64.71% | 73.33% |
| Heavy | 19 | 9 / 13 | 47.37% | 69.23% | 14 / 21 | 73.68% | 66.67% |

Aggregate micro metrics:

| Pipeline | References | Matched | Predictions | Recall | Precision | Micro F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Joint object + condition prompt | 59 | 28 | 37 | 47.46% | 75.68% | 58.33% |
| Detection-first object discovery | 59 | 42 | 58 | 71.19% | 72.41% | 71.79% |

Measured improvement from separating object discovery from condition assessment:

```text
Recall:   +23.73 percentage points
          +50.0% relative
Micro-F1: +13.46 percentage points
Precision:-3.27 percentage points
```

### Interpretation limits

These numbers are development-set results, not production benchmarks.

The current scorer uses normalized category/label matching, so granularity mismatches can affect counts. For example, a model may predict a broader concept such as `dishes` or a semantically related label where the reference inventory uses individual object categories. Reference labels are frozen before inference and are not retroactively changed to improve a result.

The heavy joint scene also exposed a reliability failure: the first provider response failed strict scene-structure validation. One retry produced the valid 13-entity result shown above. Provider completion and schema validity therefore remain separate from accuracy metrics.

Detection-first inference also increased latency in some scenes, including a 46.4-second heavy-scene call. Latency is not currently presented as a resume or production-performance metric.

## Condition-extraction development evidence

Earlier dish-load evaluation exposed numeric saturation and incomplete calibration. Those results remain useful diagnostic evidence but are not directly comparable to the scene-completeness benchmark because they evaluate a different target.

A live clean-sink integration previously persisted `dish_load = 0.0` with `confidence = NULL`. A later browser scenario on a moderate kitchen produced `dish_load = 0.76`, required explicit confirmation, and successfully drove household intelligence after user evidence was created.

## Research verification

Live Tavily search through HomHive has been verified and returned normalized source evidence. Automated tests cover research routing, API behavior, and cache behavior.

Do not claim that every Tavily call changes a household decision. Routine dishes/laundry should not require web research, and external evidence is treated as untrusted input that must remain separate from household state.

A separate live cache-hit reuse measurement has not been promoted as a runtime metric.

## Planning and replanning verification

Live NVIDIA Nemotron planning through Nebius has been verified with `nvidia/Nemotron-3_5-Lightning`.

A structured planning scenario contained plant, dish, and laundry work with a two-task cap and a 20-minute active-time budget. Nemotron selected the plant and dish tasks while deferring laundry. The selected work fit the active-time budget and contained no invented task IDs.

A second call used the same task state with only 5 available active minutes. Nemotron selected only the 5-minute plant task and deferred the 15-minute and longer tasks.

The browser end-to-end scenario separately verified:

```text
same persisted household state
+ 20 available active minutes
-> one 15-minute task selected

same persisted household state
+ 5 available active minutes
-> no 15-minute task selected
```

These checks demonstrate context-sensitive replanning, but they are not a statistically meaningful constraint-compliance benchmark.

## Docker runtime verification

The production images build successfully for FastAPI and Next.js. Docker Compose has been exercised with:

- PostgreSQL 17 healthy
- Alembic migration on backend startup
- FastAPI running on port 8000
- `/health` returning HTTP 200
- Next.js production server returning HTTP 200 on port 3001
- persistent PostgreSQL and media volumes

This is a local runtime smoke test, not a public deployment claim.

## Evaluation integrity

Do not publish fabricated accuracy, latency, reliability, cost, or scale metrics.

A metric is reportable only when:

- the evaluation set exists
- the procedure is reproducible
- the measurement was actually run
- important limitations are disclosed

The strongest current resume-safe perception statement is:

> Improved scene-entity recall from 47.5% to 71.2% (+50% relative) and micro-F1 from 58.3% to 71.8% on a human-labeled 59-entity kitchen development set by separating object discovery from condition assessment.

## October 2026 validation scope

Regression checks must cover: the same-media idempotent response, independent reviewer outcomes, corroborated versus unverified evidence labels, unknown room identity, absence of a task for healthy plants, overdue verification with no follow-up evidence, and the unchanged future-due state. Test whether a clear-sink observation supersedes older work **only** where object/room identity can be established. Do not treat a green unit suite as proof of real-scene correctness or accessibility.

# Evaluation

HomHive evaluates three different questions: what is visible, which changes are supported, and which tasks are appropriate or feasible.

## Automated checks

From `backend/`, run `python -m pytest -q`. Tests cover models and repositories, room matching, object identity, visual evidence, task deduplication, research orchestration, Nemotron output validation, and task life cycle. `npm run typecheck` and `npm run build` validate the frontend separately.

The latest reported Windows regression run before repository cleanup had **684 passing backend tests**. This documentation cleanup is not itself proof that the final runtime has been reverified.

## Development-set vision comparison

Four human-reviewed kitchen scenes contain 59 reference entities. Earlier development measurements:

| Measurement | Joint prompting | Detection-first |
| --- | ---: | ---: |
| Matched entities | 28 | 42 |
| Predicted entities | 37 | 58 |
| Micro recall | 47.46% | 71.19% |
| Micro precision | 75.68% | 72.41% |
| Micro F1 | 58.33% | 71.79% |

Detection-first improved micro recall by **23.73 percentage points** and micro F1 by **13.46 percentage points** while decreasing precision by 3.27 percentage points. These are small, domain-specific development results. They do not establish production object recognition accuracy.

The scene inventory should count physical objects/groups, fixtures, and structures/areas according to the evaluation schema. Changes in visibility and presence are distinct, and grouped items must not be counted twice. Region annotations are bounding boxes, not segmentation masks.

## Runtime verification

A provider HTTP success proves that the API request completed, but not that the right object received usable research. For the end-to-end claim, verify that sources persist, match a specific object or task, and appear as clickable links in the UI. Confirm the selected Nemotron task is one of the locally eligible IDs; a valid empty selection is acceptable when no work is feasible.

Room-to-room comparisons must be physically supported, not inferred solely from scene category. Task completion from changed images must distinguish visible goal achievement from actual physical execution.

## Known limitations

- Small reference dataset and vocabulary/granularity sensitivity.
- Real-image species identification and object-linked research display still require end-to-end proof.
- Some durations and progress values remain unverified or approximate.
- A successful automated test suite does not validate live credentials, infrastructure, or provider responses.

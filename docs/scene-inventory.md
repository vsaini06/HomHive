# Household scene inventory

An image may contain several visible objects, not only a single household problem. `app.vision.scene` supplies an **experimental, read-only inventory** that records each clearly visible object or area, its location within the image, and grounded visual evidence. The categories are open vocabulary: dishes, appliances, furniture, plants, cleaning supplies, and unfamiliar objects can be represented without inventing a new core condition category.

Object presence does **not** establish a household problem. An entity condition may be `not_assessed`, `unknown`, or an evidence-backed visible assessment. Assessed conditions require separate visible evidence. No confidence is generated, and no physical identity is assumed across images. `needs_review` indicates ambiguity.

The scene provider is deliberately separate from the existing four-condition vision adapter and observation persistence. This stage does not write to PostgreSQL, create tasks, or claim to track persistent object identities. Results can inform later evidence-based condition derivation, but do not automatically do so.

## Run locally

From `backend`, with `.env` configured:

```powershell
python -m evaluation.run_scene --image evaluation/images/kitchen_light_01.png --location kitchen --output evaluation/scene_light.json
```

The command makes one real Nebius inference call and writes only a local JSON file. Review the file manually. Keep photos and scene reports private; don't commit them. For a zero-cost validation run, use `python -m pytest -q tests/test_scene_inventory.py`.

## Evaluation notes

Measure entity recall against a human-reviewed inventory; count invented entities and unsupported condition attributes separately. Object names need consistent matching conventions, and full recall is not guaranteed when objects are tiny, hidden, or ambiguous. Do not compare object-inventory completeness with category-level severity MAE: these are separate evaluation targets. The initial kitchen condition benchmark showed five correct category detections but poor severity calibration; a subsequent rubric run completed only four of five and showed an unsupported plant-distress claim. Keep both reports as historical baselines.

Future integration needs: an explicit relation vocabulary, observation derivation rules that require corroborating evidence, stable-identity reconciliation with user confirmation, and an independent unseen-image test set. These are not implemented in this inventory stage.

## Evidence-aware scene validation

Scene locations come from the application request, not from untrusted model output. Responses may omit `location`, but if a location is supplied and disagrees with the request it is rejected.

Valid detected objects may be retained even when a separate *condition assessment* has no supporting condition evidence. In that case, the object remains in `entities` with `condition: "unknown"`; the unsupported assessment is recorded under `rejected_assessments`, and `needs_review` is set to true. No condition claim is treated as verified, and this inventory does not create domain observations or tasks.

Malformed entities, extra fields, invalid condition types, absent object evidence, invalid JSON, and mismatched locations are still rejected. The handling is a narrow, explicit exception for recognizable objects carrying condition claims without condition evidence, not generalized schema repair. A present evidence string is a structural requirement, not proof that a model's visual claim is true.

A live Nebius response was processed into a valid local JSON scene inventory after format and validation fixes. However, it returned only one entity (`drain`) for a kitchen image with many visible items. Compatibility of that individual request is demonstrated, but scene completeness and accuracy are **not**. Automated tests use simulated provider responses and do not measure visual detection recall.

## Known live behavior and follow-up

The latest live kitchen scene run produced `entities: [{label: "drain", ...}]`, `needs_review: false`, and no rejected assessments. This passes structural validation but misses several visible items; a low entity count cannot be treated as an adequate inventory. Distinguish *format success*, *validated evidence structure*, and *perceptual completeness*.

Future work should create a human-annotated object list per image and compare detection-only versus joint detection/condition prompting on separate images. Track missing objects, extra objects, unsupported condition evidence, latency, and cost. Do not merge the experimental inventory into household observation persistence until there are explicit, evaluated derivation rules.

## Integration note

Scene/category benchmark coverage and successful claim corroboration are distinct evaluations. The October 2026 live example had an unresolved room and a supported absence-of-plant-problem claim. Do not count it as successful room identification or as proof of complete scene understanding. This update does not modify image assets, canonical variant lineage, or dataset annotations.

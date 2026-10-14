from pydantic import BaseModel, ConfigDict, Field

from app.vision.scene import SceneInventory


class ReferenceEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=10)


class SceneCompletenessResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_count: int = Field(ge=0)
    prediction_count: int = Field(ge=0)
    matched_count: int = Field(ge=0)
    missed_labels: list[str]
    unsupported_labels: list[str]
    duplicate_labels: list[str]
    recall: float = Field(ge=0.0, le=1.0)
    precision: float = Field(ge=0.0, le=1.0)
    evidence_rate: float = Field(ge=0.0, le=1.0)


def _normalized(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())


def _reference_labels(reference: ReferenceEntity) -> set[str]:
    return {
        _normalized(reference.label),
        *(_normalized(alias) for alias in reference.aliases),
    }


def score_scene_inventory(
    reference: list[ReferenceEntity],
    inventory: SceneInventory,
) -> SceneCompletenessResult:
    unmatched_reference = set(range(len(reference)))
    matched_predictions: set[int] = set()
    duplicate_labels: list[str] = []

    reference_labels = [
        _reference_labels(item)
        for item in reference
    ]

    for prediction_index, entity in enumerate(inventory.entities):
        label = _normalized(entity.label)
        candidate_matches = [
            index
            for index in unmatched_reference
            if label in reference_labels[index]
        ]

        if candidate_matches:
            reference_index = min(candidate_matches)
            unmatched_reference.remove(reference_index)
            matched_predictions.add(prediction_index)
            continue

        if any(label in labels for labels in reference_labels):
            duplicate_labels.append(entity.label)

    unsupported_labels = [
        entity.label
        for index, entity in enumerate(inventory.entities)
        if index not in matched_predictions
        and entity.label not in duplicate_labels
    ]

    missed_labels = [
        reference[index].label
        for index in sorted(unmatched_reference)
    ]

    matched_count = len(matched_predictions)
    reference_count = len(reference)
    prediction_count = len(inventory.entities)
    recall = matched_count / reference_count if reference_count else 1.0
    precision = matched_count / prediction_count if prediction_count else (
        1.0 if not reference_count else 0.0
    )
    evidence_count = sum(
        1
        for entity in inventory.entities
        if entity.evidence.strip()
    )
    evidence_rate = evidence_count / prediction_count if prediction_count else 1.0

    return SceneCompletenessResult(
        reference_count=reference_count,
        prediction_count=prediction_count,
        matched_count=matched_count,
        missed_labels=missed_labels,
        unsupported_labels=unsupported_labels,
        duplicate_labels=duplicate_labels,
        recall=round(recall, 4),
        precision=round(precision, 4),
        evidence_rate=round(evidence_rate, 4),
    )

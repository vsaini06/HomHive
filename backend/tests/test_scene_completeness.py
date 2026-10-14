from app.evaluation.scene import ReferenceEntity, score_scene_inventory
from app.vision.scene import SceneEntity, SceneInventory


def scene(labels):
    return SceneInventory(
        location="kitchen",
        entities=[
            SceneEntity(
                label=label,
                area="counter",
                evidence=f"{label} is visible",
                condition="not_assessed",
            )
            for label in labels
        ],
        needs_review=False,
    )


def test_scene_completeness_scores_matches_and_misses():
    reference = [
        ReferenceEntity(label="faucet", aliases=["tap"]),
        ReferenceEntity(label="bowl"),
        ReferenceEntity(label="plant"),
    ]

    result = score_scene_inventory(reference, scene(["tap", "bowl"]))

    assert result.matched_count == 2
    assert result.missed_labels == ["plant"]
    assert result.recall == 0.6667
    assert result.precision == 1.0


def test_scene_completeness_reports_unsupported_predictions():
    result = score_scene_inventory(
        [ReferenceEntity(label="bowl")],
        scene(["bowl", "toaster"]),
    )

    assert result.unsupported_labels == ["toaster"]
    assert result.precision == 0.5


def test_scene_completeness_reports_duplicate_predictions():
    result = score_scene_inventory(
        [ReferenceEntity(label="glass", aliases=["drinking glass"])],
        scene(["glass", "drinking glass"]),
    )

    assert result.matched_count == 1
    assert result.duplicate_labels == ["drinking glass"]


def test_empty_reference_and_empty_scene_are_complete():
    inventory = SceneInventory(
        location="kitchen",
        entities=[],
        needs_review=True,
    )

    result = score_scene_inventory([], inventory)

    assert result.recall == 1.0
    assert result.precision == 1.0
    assert result.evidence_rate == 1.0

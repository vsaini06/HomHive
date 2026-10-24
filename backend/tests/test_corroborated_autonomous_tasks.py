from app.models import Observation
from app.services.reactive_tasks import decide_task_from_observation
from app.services.task_ranking import score_task


def test_multi_model_observation_creates_task_without_inventing_confidence():
    observation = Observation(
        id="verified-load", source="photo", location="unknown",
        category="laundry_load", value=0.95, confidence=None,
        metadata={"ai_verification": "multi_model_corroborated", "ai_verification_scope": "claim_level"},
    )
    decision = decide_task_from_observation(observation)
    assert decision.task is not None
    assert decision.task.confidence is None
    assert "unknown" not in decision.task.description
    assert decision.task.metadata["effort_estimate_source"] == "default_unverified"
    assert score_task(decision.task).priority_score >= 0
    second = decide_task_from_observation(observation, [decision.task])
    assert second.task is None


def test_unverified_missing_confidence_still_cannot_create_task():
    observation = Observation(id="unreviewed", source="photo", location="kitchen", category="dish_load", value=0.9, confidence=None)
    assert decide_task_from_observation(observation).task is None

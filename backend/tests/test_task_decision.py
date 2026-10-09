from app.models import (
    Observation,
    TaskDecisionReason,
)
from app.services.reactive_tasks import (
    task_from_observation,
    decide_task_from_observation,
)

#-tests-

#-1-
def test_detailed_result_reports_task_created():
    observation = Observation(
        id="obs_result_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.85,
        confidence=0.90,
    )

    result = decide_task_from_observation(observation)

    assert result.task is not None
    assert result.reason == TaskDecisionReason.TASK_CREATED

#-2-
def test_detailed_result_reports_below_threshold():
    observation = Observation(
        id="obs_result_002",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.40,
        confidence=0.95,
    )

    result = decide_task_from_observation(observation)

    assert result.task is None
    assert result.reason == TaskDecisionReason.BELOW_TRIGGER_LEVEL

#-3-
def test_detailed_result_reports_low_confidence():
    observation = Observation(
        id="obs_result_003",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.85,
        confidence=0.40,
    )

    result = decide_task_from_observation(observation)

    assert result.task is None
    assert result.reason == TaskDecisionReason.LOW_CONFIDENCE

#-4-
def test_detailed_result_reports_unsupported_category():
    observation = Observation(
        id="obs_result_004",
        source="photo",
        location="living_room",
        category="maintenance_status",
        value=0.90,
        confidence=0.95,
    )

    result = decide_task_from_observation(observation)

    assert result.task is None
    assert result.reason == TaskDecisionReason.UNSUPPORTED_CONDITION

#-5-
def test_detailed_result_reports_duplicate_active_task():
    first_observation = Observation(
        id="obs_result_005",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.85,
        confidence=0.95,
    )

    existing_task = task_from_observation(first_observation)

    second_observation = Observation(
        id="obs_result_006",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.90,
        confidence=0.96,
    )

    result = decide_task_from_observation(
        second_observation,
        existing_tasks=[existing_task],
    )

    assert result.task is None
    assert (
        result.reason
        == TaskDecisionReason.ACTIVE_TASK_ALREADY_EXISTS
    )
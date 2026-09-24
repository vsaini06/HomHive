from app.models import (
    Observation,
    TaskDiscoveryReason,
)
from app.services.task_discovery import (
    discover_task,
    discover_task_detailed,
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

    result = discover_task_detailed(observation)

    assert result.task is not None
    assert result.reason == TaskDiscoveryReason.TASK_CREATED

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

    result = discover_task_detailed(observation)

    assert result.task is None
    assert result.reason == TaskDiscoveryReason.BELOW_THRESHOLD

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

    result = discover_task_detailed(observation)

    assert result.task is None
    assert result.reason == TaskDiscoveryReason.LOW_CONFIDENCE

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

    result = discover_task_detailed(observation)

    assert result.task is None
    assert result.reason == TaskDiscoveryReason.UNSUPPORTED_CATEGORY

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

    existing_task = discover_task(first_observation)

    second_observation = Observation(
        id="obs_result_006",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.90,
        confidence=0.96,
    )

    result = discover_task_detailed(
        second_observation,
        existing_tasks=[existing_task],
    )

    assert result.task is None
    assert (
        result.reason
        == TaskDiscoveryReason.DUPLICATE_ACTIVE_TASK
    )
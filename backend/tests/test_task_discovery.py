from app.models import Observation, TaskStatus
from app.services.task_discovery import discover_task

def test_high_dish_load_creates_task():
    observation = Observation(
        id="obs_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.82,
        confidence=0.91,
    )
    task = discover_task(observation)
    assert task is not None
    assert task.source_observation_id == "obs_001"
    assert task.task_key == "kitchen:dish_load"
    assert task.description == "Clear the dishes in kitchen"
    assert task.estimated_effort_minutes == 15


def test_low_dish_load_does_not_create_task():
    observation = Observation(
        id="obs_002",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.35,
        confidence=0.94,
    )
    task = discover_task(observation)
    assert task is None


def test_high_laundry_load_creates_task():
    observation = Observation(
        id="obs_003",
        source="photo",
        location="laundry_room",
        category="laundry_load",
        value=0.85,
        confidence=0.90,
    )
    task = discover_task(observation)
    assert task is not None
    assert task.task_key == "laundry_room:laundry_load"
    assert task.description == "Do the laundry in laundry_room"
    assert task.estimated_effort_minutes == 45


def test_low_laundry_load_does_not_create_task():
    observation = Observation(
        id="obs_004",
        source="photo",
        location="laundry_room",
        category="laundry_load",
        value=0.40,
        confidence=0.92,
    )
    assert discover_task(observation) is None


def test_category_without_rule_does_not_create_task():
    observation = Observation(
        id="obs_005",
        source="photo",
        location="living_room",
        category="maintenance_status",
        value=0.90,
        confidence=0.88,
    )
    assert discover_task(observation) is None

def test_pending_duplicate_task_is_blocked():
    observation = Observation(
        id="obs_006",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.90,
        confidence=0.95,
    )
    existing_task = discover_task(observation)
    new_observation = Observation(
        id="obs_007",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.92,
        confidence=0.96,
    )
    new_task = discover_task(
        new_observation,
        existing_tasks=[existing_task],
    )
    assert new_task is None


def test_in_progress_duplicate_task_is_blocked():
    observation = Observation(
        id="obs_008",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.90,
        confidence=0.95,
    )
    existing_task = discover_task(observation)
    existing_task.status = TaskStatus.IN_PROGRESS
    new_observation = Observation(
        id="obs_009",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.95,
        confidence=0.96,
    )
    assert discover_task(
        new_observation,
        existing_tasks=[existing_task],
    ) is None


def test_completed_task_allows_new_task():
    observation = Observation(
        id="obs_010",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.85,
        confidence=0.93,
    )
    existing_task = discover_task(observation)
    existing_task.status = TaskStatus.COMPLETED
    new_observation = Observation(
        id="obs_011",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.88,
        confidence=0.94,
    )
    new_task = discover_task(
        new_observation,
        existing_tasks=[existing_task],
    )
    assert new_task is not None
    assert new_task.id == "task_obs_011"


def test_different_task_key_is_allowed():
    existing_observation = Observation(
        id="obs_012",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.90,
        confidence=0.95,
    )
    existing_task = discover_task(existing_observation)

    laundry_observation = Observation(
        id="obs_013",
        source="photo",
        location="laundry_room",
        category="laundry_load",
        value=0.90,
        confidence=0.92,
    )
    new_task = discover_task(
        laundry_observation,
        existing_tasks=[existing_task],
    )
    assert new_task is not None
    assert new_task.task_key == "laundry_room:laundry_load"

def test_high_value_high_confidence_creates_task():
    observation = Observation(
        id="obs_conf_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.85,
        confidence=0.90,
    )

    task = discover_task(observation)

    assert task is not None


def test_high_value_low_confidence_does_not_create_task():
    observation = Observation(
        id="obs_conf_002",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.85,
        confidence=0.40,
    )

    task = discover_task(observation)

    assert task is None


def test_low_value_high_confidence_does_not_create_task():
    observation = Observation(
        id="obs_conf_003",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.40,
        confidence=0.95,
    )

    task = discover_task(observation)

    assert task is None


def test_confidence_at_minimum_threshold_creates_task():
    observation = Observation(
        id="obs_conf_004",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.80,
        confidence=0.70,
    )

    task = discover_task(observation)

    assert task is not None
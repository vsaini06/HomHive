from app.models import HouseholdState, Observation, TaskStatus
from app.services.task_discovery import discover_task

#-tests-

#-1-
def test_household_observation_to_task_flow():
    state = HouseholdState(id="home_001")
    active_tasks = []

    obs_1 = Observation(
        id="obs_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.30,
        confidence=0.95,
    )

    state.add_observation(obs_1)

    task = discover_task(
        obs_1,
        existing_tasks=active_tasks,
    )

    assert task is None

    obs_2 = Observation(
        id="obs_002",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.85,
        confidence=0.93,
    )

    state.add_observation(obs_2)

    task = discover_task(
        obs_2,
        existing_tasks=active_tasks,
    )

    assert task is not None
    active_tasks.append(task)

    obs_3 = Observation(
        id="obs_003",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.90,
        confidence=0.94,
    )

    state.add_observation(obs_3)

    duplicate = discover_task(
        obs_3,
        existing_tasks=active_tasks,
    )

    assert duplicate is None

    active_tasks[0].status = TaskStatus.COMPLETED

    obs_4 = Observation(
        id="obs_004",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.80,
        confidence=0.92,
    )

    state.add_observation(obs_4)

    new_task = discover_task(
        obs_4,
        existing_tasks=active_tasks,
    )

    assert new_task is not None
    assert len(state.observation_history) == 4
    assert (
        state.current_observations["kitchen:dish_load"].id
        == "obs_004"
    )

#-2-
def test_low_confidence_observations_are_preserved_without_task():
    state = HouseholdState(id="home_002")
    active_tasks = []

    observations = [
        Observation(
            id="obs_low_001",
            source="photo",
            location="kitchen",
            category="dish_load",
            value=0.82,
            confidence=0.40,
        ),
        Observation(
            id="obs_low_002",
            source="photo",
            location="kitchen",
            category="dish_load",
            value=0.86,
            confidence=0.50,
        ),
        Observation(
            id="obs_low_003",
            source="photo",
            location="kitchen",
            category="dish_load",
            value=0.88,
            confidence=0.60,
        ),
    ]

    for observation in observations:
        state.add_observation(observation)

        task = discover_task(
            observation,
            existing_tasks=active_tasks,
        )

        assert task is None
    assert len(state.observation_history) == 3

    current = state.current_observations["kitchen:dish_load"]

    assert current.id == "obs_low_003"
    assert current.value == 0.88
    assert current.confidence == 0.60

#-3-
def test_high_confidence_observation_after_uncertain_evidence_creates_task():
    state = HouseholdState(id="home_003")
    active_tasks = []

    low_confidence_observation = Observation(
        id="obs_recovery_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.85,
        confidence=0.45,
    )

    state.add_observation(low_confidence_observation)

    first_task = discover_task(
        low_confidence_observation,
        existing_tasks=active_tasks,
    )

    assert first_task is None

    high_confidence_observation = Observation(
        id="obs_recovery_002",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.88,
        confidence=0.92,
    )

    state.add_observation(high_confidence_observation)

    second_task = discover_task(
        high_confidence_observation,
        existing_tasks=active_tasks,
    )

    assert second_task is not None
    assert second_task.source_observation_id == "obs_recovery_002"
    assert second_task.task_key == "kitchen:dish_load"
    assert len(state.observation_history) == 2

    current = state.current_observations["kitchen:dish_load"]

    assert current.id == "obs_recovery_002"
    assert current.confidence == 0.92
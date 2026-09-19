from app.models import HouseholdState, Observation, TaskStatus
from app.services.task_discovery import discover_task


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
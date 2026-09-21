from app.models import (
    HouseholdState,
    Observation,
    UrgencyLevel,
)

from app.services.task_discovery import discover_task
from app.services.task_prioritization import prioritize_tasks


def test_observations_become_prioritized_action_plan():
    state = HouseholdState(id="home_priority_001")

    observations = [
        Observation(
            id="obs_dishes",
            source="photo",
            location="kitchen",
            category="dish_load",
            value=0.85,
            confidence=0.90,
        ),
        Observation(
            id="obs_laundry",
            source="photo",
            location="laundry_room",
            category="laundry_load",
            value=0.90,
            confidence=0.95,
        ),
    ]

    discovered_tasks = []

    for observation in observations:
        state.add_observation(observation)

        task = discover_task(
            observation,
            existing_tasks=discovered_tasks,
        )

        if task is not None:
            discovered_tasks.append(task)

    assert len(state.observation_history) == 2
    assert len(discovered_tasks) == 2


    discovered_tasks[0].urgency = UrgencyLevel.HIGH
    discovered_tasks[1].urgency = UrgencyLevel.MEDIUM

    prioritized = prioritize_tasks(discovered_tasks)

    assert len(prioritized) == 2

    assert prioritized[0].task.id == "task_obs_dishes"
    assert prioritized[1].task.id == "task_obs_laundry"

    assert (
        prioritized[0].priority_score
        > prioritized[1].priority_score
    )
from app.models import (
    HouseholdState,
    Observation,
    TaskUrgency,
)

from app.services.reactive_tasks import task_from_observation
from app.services.task_ranking import rank_tasks

#-tests-

#-1-
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

        task = task_from_observation(
            observation,
            existing_tasks=discovered_tasks,
        )

        if task is not None:
            discovered_tasks.append(task)

    assert len(state.observation_history) == 2
    assert len(discovered_tasks) == 2


    discovered_tasks[0].urgency = TaskUrgency.HIGH
    discovered_tasks[1].urgency = TaskUrgency.MEDIUM

    ranked = rank_tasks(discovered_tasks)

    assert len(ranked) == 2
    assert ranked[0].task.id == "task_obs_dishes"
    assert ranked[1].task.id == "task_obs_laundry"
    assert (
        ranked[0].priority_score
        > ranked[1].priority_score
    )
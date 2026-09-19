from dataclasses import dataclass
from app.models import Observation, ObservationCategory, Task

@dataclass(frozen=True)
class TaskRule:
    threshold: float
    description: str
    effort_minutes: int

TASK_RULES = {
    ObservationCategory.DISH_LOAD: TaskRule(
        threshold=0.70,
        description="Clear the dishes in {location}",
        effort_minutes=15,
    ),
    ObservationCategory.LAUNDRY_LOAD: TaskRule(
        threshold=0.75,
        description="Do the laundry in {location}",
        effort_minutes=45,
    ),
}


def discover_task(
    observation: Observation,
    existing_tasks: list[Task] | None = None,
) -> Task | None:
    rule = TASK_RULES.get(observation.category)

    if rule is None:
        return None

    existing_tasks = existing_tasks or []

    task_key = (
        f"{observation.location}:"
        f"{observation.category.value}"
    )
    for task in existing_tasks:
        if (
            task.task_key == task_key
            and task.status.value in {"pending", "in_progress"}
        ):
            return None
        
    if observation.value < rule.threshold:
        return None

    return Task(
        id=f"task_{observation.id}",
        task_key=(
            f"{observation.location}:"
            f"{observation.category.value}"
        ),
        description=rule.description.format(
            location=observation.location
        ),
        source_observation_id=observation.id,
        urgency="medium",
        estimated_effort_minutes=rule.effort_minutes,
        confidence=observation.confidence,
    )
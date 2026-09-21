from dataclasses import dataclass
from app.models import (
    Observation,
    ObservationCategory,
    Task,
    TaskDiscoveryReason,
    TaskDiscoveryResult,
)

@dataclass(frozen=True)
class TaskRule:
    threshold: float
    min_confidence: float
    description: str
    effort_minutes: int

TASK_RULES = {
    ObservationCategory.DISH_LOAD: TaskRule(
        threshold=0.70,
        min_confidence=0.70,
        description="Clear the dishes in {location}",
        effort_minutes=15,
    ),
    ObservationCategory.LAUNDRY_LOAD: TaskRule(
        threshold=0.75,
        min_confidence=0.70,
        description="Do the laundry in {location}",
        effort_minutes=45,
    ),
}


def discover_task_detailed(
    observation: Observation,
    existing_tasks: list[Task] | None = None,
) -> TaskDiscoveryResult:
    rule = TASK_RULES.get(observation.category)

    if rule is None:
        return TaskDiscoveryResult(
            task=None,
            reason=TaskDiscoveryReason.UNSUPPORTED_CATEGORY,
        )

    if observation.value < rule.threshold:
        return TaskDiscoveryResult(
            task=None,
            reason=TaskDiscoveryReason.BELOW_THRESHOLD,
        )

    if observation.confidence < rule.min_confidence:
        return TaskDiscoveryResult(
            task=None,
            reason=TaskDiscoveryReason.LOW_CONFIDENCE,
        )

    task_key = (
        f"{observation.location}:"
        f"{observation.category.value}"
    )

    existing_tasks = existing_tasks or []

    for task in existing_tasks:
        if (
            task.task_key == task_key
            and task.status.value in {"pending", "in_progress"}
        ):
            return TaskDiscoveryResult(
                task=None,
                reason=TaskDiscoveryReason.DUPLICATE_ACTIVE_TASK,
            )

    task = Task(
        id=f"task_{observation.id}",
        task_key=task_key,
        description=rule.description.format(
            location=observation.location
        ),
        source_observation_id=observation.id,
        urgency="medium",
        estimated_effort_minutes=rule.effort_minutes,
        confidence=observation.confidence,
    )

    return TaskDiscoveryResult(
        task=task,
        reason=TaskDiscoveryReason.TASK_CREATED,
    )


def discover_task(
    observation: Observation,
    existing_tasks: list[Task] | None = None,
) -> Task | None:
    result = discover_task_detailed(
        observation,
        existing_tasks=existing_tasks,
    )

    return result.task
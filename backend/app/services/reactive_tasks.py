from dataclasses import dataclass

from app.models import (
    ConditionType,
    Observation,
    Task,
    TaskDecision,
    TaskDecisionReason,
    TaskStatus,
    TaskUrgency,
)


@dataclass(frozen=True)
class TaskTrigger:
    """The minimum evidence needed before one condition should create work."""

    trigger_level: float
    min_confidence: float
    description_template: str
    effort_minutes: int


TASK_TRIGGERS = {
    ConditionType.DISH_LOAD: TaskTrigger(
        trigger_level=0.70,
        min_confidence=0.70,
        description_template=(
            "Clear the dishes in {location}"
        ),
        effort_minutes=15,
    ),
    ConditionType.LAUNDRY_LOAD: TaskTrigger(
        trigger_level=0.75,
        min_confidence=0.70,
        description_template=(
            "Do the laundry in {location}"
        ),
        effort_minutes=45,
    ),
}


def _active_task_exists(
    task_key: str,
    existing_tasks: list[Task],
) -> bool:
    """Check whether this household work is already waiting or underway."""

    return any(
        task.task_key == task_key
        and task.status in {
            TaskStatus.PENDING,
            TaskStatus.IN_PROGRESS,
        }
        for task in existing_tasks
    )


def decide_task_from_observation(
    observation: Observation,
    existing_tasks: list[Task] | None = None,
) -> TaskDecision:
    """Decide whether one household observation should create a task."""

    trigger = TASK_TRIGGERS.get(
        observation.category
    )

    if trigger is None:
        return TaskDecision(
            task=None,
            reason=(
                TaskDecisionReason.UNSUPPORTED_CONDITION
            ),
        )

    # A condition should cross its configured level before it creates work.
    if observation.value < trigger.trigger_level:
        return TaskDecision(
            task=None,
            reason=(
                TaskDecisionReason.BELOW_TRIGGER_LEVEL
            ),
        )

    # Strong condition values are not enough if the observation itself is weak.
    if (
        observation.confidence
        < trigger.min_confidence
    ):
        return TaskDecision(
            task=None,
            reason=TaskDecisionReason.LOW_CONFIDENCE,
        )

    task_key = (
        f"{observation.location}:"
        f"{observation.category.value}"
    )

    active_tasks = existing_tasks or []

    # Repeated observations should not keep creating the same unresolved work.
    if _active_task_exists(
        task_key=task_key,
        existing_tasks=active_tasks,
    ):
        return TaskDecision(
            task=None,
            reason=(
                TaskDecisionReason.ACTIVE_TASK_ALREADY_EXISTS
            ),
        )

    task = Task(
        id=f"task_{observation.id}",
        task_key=task_key,
        description=(
            trigger.description_template.format(
                location=observation.location
            )
        ),
        source_observation_id=observation.id,
        urgency=TaskUrgency.MEDIUM,
        estimated_effort_minutes=(
            trigger.effort_minutes
        ),
        confidence=observation.confidence,
    )

    return TaskDecision(
        task=task,
        reason=TaskDecisionReason.TASK_CREATED,
    )


def task_from_observation(
    observation: Observation,
    existing_tasks: list[Task] | None = None,
) -> Task | None:
    """Return the task created from an observation, if the evidence warrants one."""

    decision = decide_task_from_observation(
        observation=observation,
        existing_tasks=existing_tasks,
    )

    return decision.task
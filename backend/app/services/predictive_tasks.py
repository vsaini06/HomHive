from app.models import (
    ActionDecision,
    ActionState,
    Task,
    TaskStatus,
    TaskUrgency,
)


def _predictive_task_key(
    decision: ActionDecision,
) -> str:
    """Build the current identity used for prediction-driven household work."""

    return (
        f"predictive:"
        f"{decision.location}:"
        f"{decision.category.value}"
    )


def task_from_action_decision(
    decision: ActionDecision,
) -> Task | None:
    """Turn an actionable forecast decision into household work."""

    if decision.status in {
        ActionState.NONE,
        ActionState.MONITOR,
    }:
        return None

    if decision.status == ActionState.ACT_NOW:
        task_urgency = TaskUrgency.HIGH
    else:
        task_urgency = TaskUrgency.MEDIUM

    condition_key = (
        f"{decision.location}:"
        f"{decision.category.value}"
    )

    task_key = _predictive_task_key(
        decision
    )

    return Task(
        id=f"predictive_task_{condition_key}",
        task_key=task_key,
        description=(
            f"Address predicted "
            f"{decision.category.value} issue "
            f"in {decision.location}"
        ),

        # This task comes from several observations and a forecast,
        # so assigning one observation as its source would be misleading.
        source_observation_id=None,

        urgency=task_urgency,
        estimated_effort_minutes=15,
        deadline=None,
        confidence=decision.confidence,

        # Keep the existing metadata keys stable until callers are migrated.
        metadata={
            "source": "intervention_prediction",
            "intervention_status": (
                decision.status.value
            ),
            "hours_to_threshold": (
                decision.hours_to_threshold
            ),
            "state_key": condition_key,
            "reason": decision.reason,
        },
    )


def update_or_create_predictive_task(
    candidate_task: Task | None,
    existing_tasks: list[Task],
) -> Task | None:
    """Refresh the matching predictive task, or return the new one if none exists."""

    if candidate_task is None:
        return None

    existing_task = next(
        (
            task
            for task in existing_tasks
            if task.task_key
            == candidate_task.task_key
        ),
        None,
    )

    if existing_task is None:
        return candidate_task

    # Forecasts change over time, but the underlying household work is the same.
    existing_task.description = (
        candidate_task.description
    )
    existing_task.urgency = (
        candidate_task.urgency
    )
    existing_task.estimated_effort_minutes = (
        candidate_task.estimated_effort_minutes
    )
    existing_task.deadline = (
        candidate_task.deadline
    )
    existing_task.confidence = (
        candidate_task.confidence
    )
    existing_task.metadata = (
        candidate_task.metadata.copy()
    )

    return existing_task


def sync_predictive_task(
    decision: ActionDecision,
    existing_tasks: list[Task],
) -> Task | None:
    """Keep predictive work aligned with the latest action decision."""

    task_key = _predictive_task_key(
        decision
    )

    existing_task = next(
        (
            task
            for task in existing_tasks
            if task.task_key == task_key
        ),
        None,
    )

    if decision.status in {
        ActionState.NONE,
        ActionState.MONITOR,
    }:
        if existing_task is None:
            return None

        # Keep the task instead of deleting it so its lifecycle can be
        # preserved once durable task history is introduced.
        existing_task.status = (
            TaskStatus.DISMISSED
        )

        existing_task.metadata[
            "intervention_status"
        ] = decision.status.value

        existing_task.metadata[
            "hours_to_threshold"
        ] = decision.hours_to_threshold

        existing_task.metadata[
            "reason"
        ] = decision.reason

        return existing_task

    candidate_task = (
        task_from_action_decision(
            decision
        )
    )

    if candidate_task is None:
        return None

    # A condition can become actionable again after previously improving.
    if existing_task is not None:
        existing_task.status = (
            TaskStatus.PENDING
        )

    return update_or_create_predictive_task(
        candidate_task=candidate_task,
        existing_tasks=existing_tasks,
    )
from app.models import (
    InterventionDecision,
    InterventionStatus,
    Task,
    TaskStatus,
    UrgencyLevel,
)


def discover_intervention_task(
    decision: InterventionDecision,
) -> Task | None:
    if decision.status in {
        InterventionStatus.NONE,
        InterventionStatus.MONITOR,
    }:
        return None

    if decision.status == InterventionStatus.ACT_NOW:
        urgency = UrgencyLevel.HIGH
    else:
        urgency = UrgencyLevel.MEDIUM

    state_key = (
        f"{decision.location}:"
        f"{decision.category.value}"
    )

    task_key = (
        f"predictive:"
        f"{decision.location}:"
        f"{decision.category.value}"
    )

    return Task(
        id=f"predictive_task_{state_key}",
        task_key=task_key,
        description=(
            f"Address predicted "
            f"{decision.category.value} issue "
            f"in {decision.location}"
        ),
        source_observation_id=None,
        urgency=urgency,
        estimated_effort_minutes=15,
        deadline=None,
        confidence=decision.confidence,
        metadata={
            "source": "intervention_prediction",
            "intervention_status": (
                decision.status.value
            ),
            "hours_to_threshold": (
                decision.hours_to_threshold
            ),
            "state_key": state_key,
            "reason": decision.reason,
        },
    )

def reconcile_intervention_task(
    discovered_task: Task | None,
    existing_tasks: list[Task],
) -> Task | None:
    if discovered_task is None:
        return None

    existing_task = next(
        (
            task
            for task in existing_tasks
            if task.task_key
            == discovered_task.task_key
        ),
        None,
    )

    if existing_task is None:
        return discovered_task

    existing_task.description = (
        discovered_task.description
    )

    existing_task.urgency = (
        discovered_task.urgency
    )

    existing_task.estimated_effort_minutes = (
        discovered_task.estimated_effort_minutes
    )

    existing_task.deadline = (
        discovered_task.deadline
    )

    existing_task.confidence = (
        discovered_task.confidence
    )

    existing_task.metadata = (
        discovered_task.metadata.copy()
    )

    return existing_task

def reconcile_intervention_decision(
    decision: InterventionDecision,
    existing_tasks: list[Task],
) -> Task | None:
    task_key = (
        f"predictive:"
        f"{decision.location}:"
        f"{decision.category.value}"
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
        InterventionStatus.NONE,
        InterventionStatus.MONITOR,
    }:
        if existing_task is None:
            return None

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

    discovered_task = (
        discover_intervention_task(
            decision
        )
    )

    if discovered_task is None:
        return None

    if existing_task is not None:
        existing_task.status = (
            TaskStatus.PENDING
        )

    return reconcile_intervention_task(
        discovered_task=discovered_task,
        existing_tasks=existing_tasks,
    )
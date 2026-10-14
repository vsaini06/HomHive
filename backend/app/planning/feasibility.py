from app.models import ScoredTask, Task

from .models import (
    DeferredTask,
    HouseholdPlan,
    NoiseLevel,
    PlanStep,
    PlanningContext,
    TaskExecutionProfile,
    TaskFeasibility,
)


def execution_profile_for_task(task: Task) -> TaskExecutionProfile:
    metadata = task.metadata

    if "active_minutes" in metadata:
        active_minutes = int(metadata["active_minutes"])
    elif task.task_key.endswith(":laundry_load"):
        active_minutes = min(5, task.estimated_effort_minutes)
    else:
        active_minutes = task.estimated_effort_minutes

    if "passive_minutes" in metadata:
        passive_minutes = int(metadata["passive_minutes"])
    elif task.task_key.endswith(":laundry_load"):
        passive_minutes = max(0, task.estimated_effort_minutes - active_minutes)
    else:
        passive_minutes = 0

    noise_value = metadata.get("noise_level", "normal")
    try:
        noise_level = NoiseLevel(noise_value)
    except ValueError:
        noise_level = NoiseLevel.NORMAL

    requires_home = bool(metadata.get("requires_home", True))

    return TaskExecutionProfile(
        task_id=task.id,
        active_minutes=max(1, active_minutes),
        passive_minutes=max(0, passive_minutes),
        noise_level=noise_level,
        requires_home=requires_home,
    )


def evaluate_task_feasibility(
    profile: TaskExecutionProfile,
    context: PlanningContext,
) -> TaskFeasibility:
    if profile.requires_home and not context.at_home:
        return TaskFeasibility(
            task_id=profile.task_id,
            feasible=False,
            reason="requires presence at home",
            active_minutes=profile.active_minutes,
            passive_minutes=profile.passive_minutes,
        )

    if context.quiet_hours_active and profile.noise_level == NoiseLevel.NOISY:
        return TaskFeasibility(
            task_id=profile.task_id,
            feasible=False,
            reason="blocked by quiet hours",
            active_minutes=profile.active_minutes,
            passive_minutes=profile.passive_minutes,
        )

    if profile.active_minutes > context.available_minutes:
        return TaskFeasibility(
            task_id=profile.task_id,
            feasible=False,
            reason="not enough active time available",
            active_minutes=profile.active_minutes,
            passive_minutes=profile.passive_minutes,
        )

    return TaskFeasibility(
        task_id=profile.task_id,
        feasible=True,
        reason="fits current execution constraints",
        active_minutes=profile.active_minutes,
        passive_minutes=profile.passive_minutes,
    )


def build_deterministic_plan(
    ranked_tasks: list[ScoredTask],
    context: PlanningContext,
) -> tuple[HouseholdPlan, list[TaskFeasibility]]:
    feasibility = []
    task_by_id = {item.task.id: item.task for item in ranked_tasks}
    remaining_minutes = context.available_minutes
    steps = []
    deferred = []

    for scored in ranked_tasks:
        profile = execution_profile_for_task(scored.task)
        assessment = evaluate_task_feasibility(profile, context)
        feasibility.append(assessment)

        if not assessment.feasible:
            deferred.append(DeferredTask(task_id=scored.task.id, reason=assessment.reason))
            continue

        if len(steps) >= context.max_tasks:
            deferred.append(DeferredTask(task_id=scored.task.id, reason="plan task limit reached"))
            continue

        if profile.active_minutes > remaining_minutes:
            deferred.append(DeferredTask(task_id=scored.task.id, reason="does not fit remaining active time"))
            continue

        remaining_minutes -= profile.active_minutes
        steps.append(
            PlanStep(
                task_id=scored.task.id,
                order=len(steps) + 1,
                reason=f"priority score {scored.priority_score:.4f} and currently executable",
                active_minutes=profile.active_minutes,
                passive_minutes=profile.passive_minutes,
            )
        )

    summary = (
        f"{len(steps)} task(s) fit the current {context.available_minutes}-minute window."
        if steps
        else "No active household task fits the current execution constraints."
    )

    return (
        HouseholdPlan(
            summary=summary,
            steps=steps,
            deferred=deferred,
            planner="deterministic",
        ),
        feasibility,
    )

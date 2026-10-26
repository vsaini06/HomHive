from datetime import datetime, timezone
import os

from app.models import (
    ConditionForecast,
    HouseholdIntelligence,
    Observation,
    Task,
    TaskStatus,
)
from app.repositories.observation_storage import ObservationStorage
from app.repositories.task_storage import TaskStorage

from .action_policy import decide_action
from .condition_tracking import build_household_condition_snapshots
from .household_state_reconstruction import reconstruct_household_state
from .predictive_tasks import sync_predictive_task
from .reactive_tasks import TASK_TRIGGERS, decide_task_from_observation
from .state_forecasting import build_condition_forecast, forecast_threshold_crossing
from .task_ranking import rank_tasks


def _qualified_history(observations: list[Observation], state_key: str) -> list[Observation]:
    return [
        observation
        for observation in observations
        if observation.state_key() == state_key and observation.confidence is not None
    ]


def _persist_task(
    household_id: str,
    candidate: Task,
    existing: list[Task],
    storage: TaskStorage,
) -> Task:
    stored = next((task for task in existing if task.id == candidate.id), None)
    if stored is None:
        saved = storage.add_task(household_id, candidate)
        existing.append(saved)
        return saved

    return storage.save_task(household_id, candidate)


def _still_deferred(value: object, now: datetime) -> bool:
    if not isinstance(value, str):
        return False
    try:
        until = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return until.tzinfo is not None and until > now
    except ValueError:
        return False


def refresh_household_intelligence(
    household_id: str,
    observations: ObservationStorage,
    tasks: TaskStorage,
    forecast_hours: float = 24.0,
) -> HouseholdIntelligence:
    state = reconstruct_household_state(household_id, observations)
    existing_tasks = tasks.list_tasks(household_id)
    # An explicit refresh advances overdue verification using only available
    # trusted evidence; a user's completion report never counts as proof.
    from app.automation.verification import evaluate, parse_time
    now = datetime.now(timezone.utc)
    for task in existing_tasks:
        meta = task.metadata
        due_at = parse_time(meta.get("verification_due_at"))
        if (meta.get("user_reported_complete_at") and due_at is not None
                and due_at <= now and meta.get("verification_status")
                not in {"verified_resolved", "verified_persisting", "expired"}):
            updated = evaluate(task, household_id, observations, now)
            tasks.save_task(household_id, updated)

    open_world_only = os.environ.get("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "").lower() == "true"
    for observation in ([] if open_world_only else state.current_observations.values()):
        key = f"{observation.location}:{observation.category.value}"
        # Keep a human dismissal of this condition, including a re-upload,
        # instead of recreating the same unresolved work on refresh.
        if any(
            task.task_key == key and task.status == TaskStatus.DISMISSED
            and task.metadata.get("dismissed_at")
            for task in existing_tasks
        ):
            continue
        decision = decide_task_from_observation(observation, existing_tasks)
        if decision.task is not None:
            _persist_task(household_id, decision.task, existing_tasks, tasks)

    snapshots_by_key = build_household_condition_snapshots(state)
    forecasts: list[ConditionForecast] = []
    action_decisions = []

    for state_key, snapshot in snapshots_by_key.items():
        history = _qualified_history(state.observation_history, state_key)
        if not history:
            continue

        forecasts.append(build_condition_forecast(snapshot, history, forecast_hours))

        trigger = TASK_TRIGGERS.get(snapshot.category)
        if trigger is None:
            continue

        if open_world_only:
            continue
        crossing = forecast_threshold_crossing(snapshot, history, trigger.trigger_level)
        decision = decide_action(crossing)
        if decision is None:
            continue

        action_decisions.append(decision)
        # One household condition represents one physical chore. Forecasts
        # still exist, but do not create a competing actionable proposal.
        key = f"{decision.location}:{decision.category.value}"
        if any(
            task.task_key == key and task.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}
            for task in existing_tasks
        ):
            continue
        if any(
            task.task_key in {key, f"predictive:{key}"}
            and task.status == TaskStatus.DISMISSED
            and task.metadata.get("dismissed_at")
            for task in existing_tasks
        ):
            continue
        predictive_task = sync_predictive_task(decision, existing_tasks)
        if predictive_task is not None:
            _persist_task(household_id, predictive_task, existing_tasks, tasks)

    all_tasks = tasks.list_tasks(household_id)
    now = datetime.now(timezone.utc)
    # Preserve predictive history, but show only one actionable task per
    # household condition. Prefer an observation-backed task when present.
    observation_keys = {
        task.task_key for task in all_tasks
        if task.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}
        and not task.task_key.startswith("predictive:")
    }
    active_tasks = [
        task
        for task in all_tasks
        if task.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}
        and not (
            task.task_key.startswith("predictive:")
            and task.task_key.removeprefix("predictive:") in observation_keys
        )
        and not (
            task.status == TaskStatus.PENDING
            and task.metadata.get("deferred_until")
            and _still_deferred(task.metadata["deferred_until"], now)
        )
    ]

    return HouseholdIntelligence(
        household_id=household_id,
        state=state,
        snapshots=list(snapshots_by_key.values()),
        forecasts=forecasts,
        action_decisions=action_decisions,
        tasks=all_tasks,
        ranked_tasks=rank_tasks(active_tasks),
    )

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


def refresh_household_intelligence(
    household_id: str,
    observations: ObservationStorage,
    tasks: TaskStorage,
    forecast_hours: float = 24.0,
) -> HouseholdIntelligence:
    state = reconstruct_household_state(household_id, observations)
    existing_tasks = tasks.list_tasks(household_id)

    for observation in state.current_observations.values():
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

        crossing = forecast_threshold_crossing(snapshot, history, trigger.trigger_level)
        decision = decide_action(crossing)
        if decision is None:
            continue

        action_decisions.append(decision)
        predictive_task = sync_predictive_task(decision, existing_tasks)
        if predictive_task is not None:
            _persist_task(household_id, predictive_task, existing_tasks, tasks)

    all_tasks = tasks.list_tasks(household_id)
    active_tasks = [
        task
        for task in all_tasks
        if task.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}
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

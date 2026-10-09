from .condition_tracking import (
    build_condition_snapshot,
    build_household_condition_snapshots,
    detect_condition_trend,
    observation_weight,
    recency_weight,
)

from .reactive_tasks import (
    TASK_TRIGGERS,
    TaskTrigger,
    decide_task_from_observation,
    task_from_observation,
)

from .task_ranking import (
    rank_tasks,
    score_task,
)

from .entity_resolution import (
    assess_entity_match,
    candidate_can_match_entity,
    resolve_entity,
    resolve_entity_candidate,
)

from .household_entity_service import (
    HouseholdEntityService,
)

from .state_forecasting import (
    build_condition_forecast,
    estimate_forecast_confidence,
    estimate_hourly_change,
    estimate_hours_to_threshold,
    forecast_threshold_crossing,
    project_condition_level,
)

from .action_policy import (
    decide_action,
)

from .predictive_tasks import (
    sync_predictive_task,
    task_from_action_decision,
    update_or_create_predictive_task,
)


__all__ = [
    # Condition tracking
    "build_condition_snapshot",
    "build_household_condition_snapshots",
    "detect_condition_trend",
    "observation_weight",
    "recency_weight",

    # Observation-driven tasks
    "TaskTrigger",
    "TASK_TRIGGERS",
    "decide_task_from_observation",
    "task_from_observation",

    # Task ranking
    "score_task",
    "rank_tasks",

    # Household entity resolution
    "candidate_can_match_entity",
    "assess_entity_match",
    "resolve_entity",
    "resolve_entity_candidate",

    # Household entity application service
    "HouseholdEntityService",

    # Condition forecasting
    "estimate_hourly_change",
    "project_condition_level",
    "build_condition_forecast",
    "estimate_hours_to_threshold",
    "forecast_threshold_crossing",
    "estimate_forecast_confidence",

    # Action policy
    "decide_action",

    # Prediction-driven tasks
    "task_from_action_decision",
    "update_or_create_predictive_task",
    "sync_predictive_task",
]

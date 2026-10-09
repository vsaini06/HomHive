from app.models import (
    ActionDecision,
    ActionState,
    ConditionType,
    TaskUrgency,
    TaskStatus,
)
from app.services import (
    task_from_action_decision,
    sync_predictive_task,
    update_or_create_predictive_task,
)

#-tests-

#-1-
def test_monitor_action_does_not_create_task():
    decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.MONITOR,
        hours_to_threshold=12.0,
        confidence=0.70,
        reason="threshold prediction is outside planning window",
    )

    task = task_from_action_decision(
        decision
    )

    assert task is None

#-2-
def test_plan_action_creates_task():
    decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=3.0,
        confidence=0.80,
        reason="threshold predicted within planning window",
    )

    task = task_from_action_decision(
        decision
    )

    assert task is not None

    assert task.urgency == TaskUrgency.MEDIUM
    assert task.confidence == 0.80

    assert (
        task.metadata["source"]
        == "intervention_prediction"
    )

    assert (
        task.metadata["hours_to_threshold"]
        == 3.0
    )
    assert (
        task.task_key
        == "predictive:kitchen:dish_load"
    )

    assert task.source_observation_id is None

#-3-
def test_act_now_action_creates_high_urgency_task():
    decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.ACT_NOW,
        hours_to_threshold=0.0,
        confidence=0.90,
        reason="threshold already reached",
    )

    task = task_from_action_decision(
        decision
    )

    assert task is not None

    assert (
        task.urgency
        == TaskUrgency.HIGH
    )

    assert (
        task.metadata["intervention_status"]
        == "act_now"
    )

#-4-
def test_predictive_task_id_is_deterministic():
    decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=3.0,
        confidence=0.80,
        reason="threshold predicted within planning window",
    )

    first_task = task_from_action_decision(
        decision
    )

    second_task = task_from_action_decision(
        decision
    )

    assert first_task is not None
    assert second_task is not None

    assert first_task.id == second_task.id

#-5-
def test_same_state_produces_same_task_key():
    first_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=6.0,
        confidence=0.70,
        reason="threshold predicted within planning window",
    )

    second_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.ACT_NOW,
        hours_to_threshold=0.0,
        confidence=0.90,
        reason="threshold already reached",
    )

    first_task = task_from_action_decision(
        first_decision
    )

    second_task = task_from_action_decision(
        second_decision
    )

    assert first_task is not None
    assert second_task is not None
    assert (
        first_task.task_key
        == second_task.task_key
    )
    assert (
        first_task.id
        == second_task.id
    )

#-6-
def test_different_states_produce_different_task_keys():
    dish_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=3.0,
        confidence=0.80,
        reason="threshold predicted within planning window",
    )

    laundry_decision = ActionDecision(
        location="laundry_room",
        category=ConditionType.LAUNDRY_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=3.0,
        confidence=0.80,
        reason="threshold predicted within planning window",
    )

    dish_task = task_from_action_decision(
        dish_decision
    )

    laundry_task = task_from_action_decision(
        laundry_decision
    )

    assert dish_task is not None
    assert laundry_task is not None
    assert (
        dish_task.task_key
        != laundry_task.task_key
    )

#-7-
def test_predictive_task_sync_returns_new_task_when_no_matching_task_exists():
    decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=3.0,
        confidence=0.80,
        reason="threshold predicted within planning window",
    )

    candidate_task = task_from_action_decision(
        decision
    )

    result = update_or_create_predictive_task(
        candidate_task=candidate_task,
        existing_tasks=[],
    )

    assert result is not None
    assert result is candidate_task
    assert (
        result.task_key
        == "predictive:kitchen:dish_load"
    )

#-8-
def test_predictive_task_sync_updates_existing_predictive_task():
    initial_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=6.0,
        confidence=0.70,
        reason="threshold predicted within planning window",
    )

    initial_task = task_from_action_decision(
        initial_decision
    )

    assert initial_task is not None

    updated_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.ACT_NOW,
        hours_to_threshold=0.0,
        confidence=0.90,
        reason="threshold already reached",
    )

    candidate_task = task_from_action_decision(
        updated_decision
    )

    result = update_or_create_predictive_task(
        candidate_task=candidate_task,
        existing_tasks=[initial_task],
    )

    assert result is not None

    assert result is initial_task

    assert (
        result.task_key
        == "predictive:kitchen:dish_load"
    )

    assert result.urgency == TaskUrgency.HIGH

    assert result.confidence == 0.90

    assert (
        result.metadata["intervention_status"]
        == "act_now"
    )

    assert (
        result.metadata["hours_to_threshold"]
        == 0.0
    )

#-9-
def test_predictive_task_sync_does_not_update_unrelated_task():
    laundry_decision = ActionDecision(
        location="laundry_room",
        category=ConditionType.LAUNDRY_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=4.0,
        confidence=0.75,
        reason="threshold predicted within planning window",
    )

    laundry_task = task_from_action_decision(
        laundry_decision
    )

    assert laundry_task is not None

    kitchen_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.ACT_NOW,
        hours_to_threshold=0.0,
        confidence=0.90,
        reason="threshold already reached",
    )

    kitchen_task = task_from_action_decision(
        kitchen_decision
    )

    result = update_or_create_predictive_task(
        candidate_task=kitchen_task,
        existing_tasks=[laundry_task],
    )

    assert result is not None

    assert result is kitchen_task

    assert (
        laundry_task.task_key
        == "predictive:laundry_room:laundry_load"
    )

    assert (
        laundry_task.urgency
        == TaskUrgency.MEDIUM
    )

    assert (
        laundry_task.confidence
        == 0.75
    )

#-10-
def test_predictive_task_sync_returns_none_without_candidate_task():
    result = update_or_create_predictive_task(
        candidate_task=None,
        existing_tasks=[],
    )

    assert result is None

#-11-
def test_monitor_dismisses_existing_predictive_task():
    plan_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=3.0,
        confidence=0.80,
        reason="threshold predicted within planning window",
    )

    existing_task = (
        task_from_action_decision(
            plan_decision
        )
    )

    assert existing_task is not None

    monitor_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.MONITOR,
        hours_to_threshold=12.0,
        confidence=0.70,
        reason="threshold prediction is outside planning window",
    )

    result = sync_predictive_task(
        decision=monitor_decision,
        existing_tasks=[existing_task],
    )

    assert result is existing_task
    assert result.status == TaskStatus.DISMISSED

    assert (
        result.metadata["intervention_status"]
        == "monitor"
    )

    assert (
        result.metadata["hours_to_threshold"]
        == 12.0
    )

#-12-
def test_monitor_does_not_create_new_task():
    decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.MONITOR,
        hours_to_threshold=12.0,
        confidence=0.70,
        reason="threshold prediction is outside planning window",
    )

    result = sync_predictive_task(
        decision=decision,
        existing_tasks=[],
    )

    assert result is None

#-13-
def test_actionable_decision_reactivates_dismissed_task():
    plan_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=3.0,
        confidence=0.80,
        reason="threshold predicted within planning window",
    )

    existing_task = (
        task_from_action_decision(
            plan_decision
        )
    )

    assert existing_task is not None

    existing_task.status = (
        TaskStatus.DISMISSED
    )

    act_now_decision = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.ACT_NOW,
        hours_to_threshold=0.0,
        confidence=0.90,
        reason="threshold already reached",
    )

    result = sync_predictive_task(
        decision=act_now_decision,
        existing_tasks=[existing_task],
    )

    assert result is existing_task

    assert result.status == TaskStatus.PENDING

    assert result.urgency == TaskUrgency.HIGH

    assert result.confidence == 0.90

    assert (
        result.metadata["intervention_status"]
        == "act_now"
    )

#-14-
def test_monitor_does_not_dismiss_unrelated_task():
    laundry_decision = ActionDecision(
        location="laundry_room",
        category=ConditionType.LAUNDRY_LOAD,
        status=ActionState.PLAN,
        hours_to_threshold=3.0,
        confidence=0.80,
        reason="threshold predicted within planning window",
    )

    laundry_task = (
        task_from_action_decision(
            laundry_decision
        )
    )

    assert laundry_task is not None

    kitchen_monitor = ActionDecision(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        status=ActionState.MONITOR,
        hours_to_threshold=12.0,
        confidence=0.70,
        reason="threshold prediction is outside planning window",
    )

    result = sync_predictive_task(
        decision=kitchen_monitor,
        existing_tasks=[laundry_task],
    )

    assert result is None

    assert (
        laundry_task.status
        == TaskStatus.PENDING
    )

#-15-



from datetime import (
    datetime,
    timezone,
)

import pytest

from app.models import (
    ActionState,
    ConditionType,
    ThresholdCrossing,
)
from app.services import decide_action

#-tests-

#-1-
def test_action_policy_acts_now_when_threshold_reached():
    crossing = ThresholdCrossing(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.95,
        threshold=0.90,
        rate_per_hour=0.10,
        hours_to_threshold=0.0,
        predicted_crossing_at=datetime.now(
            timezone.utc
        ),
        confidence=0.80,
    )
    decision = decide_action(
        crossing
    )

    assert decision is not None
    assert (
        decision.status
        == ActionState.ACT_NOW
    )

#-2-
def test_action_policy_plans_for_near_confident_prediction():
    crossing = ThresholdCrossing(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.70,
        threshold=0.90,
        rate_per_hour=0.10,
        hours_to_threshold=2.0,
        predicted_crossing_at=datetime.now(
            timezone.utc
        ),
        confidence=0.80,
    )
    decision = decide_action(
        crossing
    )

    assert decision is not None
    assert (
        decision.status
        == ActionState.PLAN
    )

#-3-
def test_action_policy_monitors_low_confidence_prediction():
    crossing = ThresholdCrossing(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.70,
        threshold=0.90,
        rate_per_hour=0.10,
        hours_to_threshold=2.0,
        predicted_crossing_at=datetime.now(
            timezone.utc
        ),
        confidence=0.30,
    )
    decision = decide_action(
        crossing
    )

    assert decision is not None
    assert (
        decision.status
        == ActionState.MONITOR
    )

#-4-
def test_action_policy_monitors_distant_prediction():
    crossing = ThresholdCrossing(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.50,
        threshold=0.90,
        rate_per_hour=0.01,
        hours_to_threshold=40.0,
        predicted_crossing_at=datetime.now(
            timezone.utc
        ),
        confidence=0.80,
    )
    decision = decide_action(
        crossing
    )

    assert decision is not None
    assert (
        decision.status
        == ActionState.MONITOR
    )

#-5-
def test_action_policy_returns_none_without_prediction():
    decision = decide_action(
        None
    )

    assert decision is None

#-6-
def test_action_policy_rejects_invalid_minimum_confidence():
    with pytest.raises(
        ValueError,
        match=(
            "Minimum confidence must be "
            "between 0 and 1."
        ),
    ):
        decide_action(
            None,
            min_confidence=1.20,
        )

#-7-

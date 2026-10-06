from datetime import (
    datetime,
    timezone,
)

import pytest

from app.models import (
    InterventionStatus,
    ObservationCategory,
    ThresholdPrediction,
)
from app.services import decide_intervention

#-tests-

#-1-
def test_intervention_acts_now_when_threshold_reached():
    prediction = ThresholdPrediction(
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        current_value=0.95,
        threshold=0.90,
        rate_per_hour=0.10,
        hours_to_threshold=0.0,
        predicted_crossing_at=datetime.now(
            timezone.utc
        ),
        confidence=0.80,
    )
    decision = decide_intervention(
        prediction
    )

    assert decision is not None
    assert (
        decision.status
        == InterventionStatus.ACT_NOW
    )

#-2-
def test_intervention_plans_for_near_confident_prediction():
    prediction = ThresholdPrediction(
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        current_value=0.70,
        threshold=0.90,
        rate_per_hour=0.10,
        hours_to_threshold=2.0,
        predicted_crossing_at=datetime.now(
            timezone.utc
        ),
        confidence=0.80,
    )
    decision = decide_intervention(
        prediction
    )

    assert decision is not None
    assert (
        decision.status
        == InterventionStatus.PLAN
    )

#-3-
def test_intervention_monitors_low_confidence_prediction():
    prediction = ThresholdPrediction(
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        current_value=0.70,
        threshold=0.90,
        rate_per_hour=0.10,
        hours_to_threshold=2.0,
        predicted_crossing_at=datetime.now(
            timezone.utc
        ),
        confidence=0.30,
    )
    decision = decide_intervention(
        prediction
    )

    assert decision is not None
    assert (
        decision.status
        == InterventionStatus.MONITOR
    )

#-4-
def test_intervention_monitors_distant_prediction():
    prediction = ThresholdPrediction(
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        current_value=0.50,
        threshold=0.90,
        rate_per_hour=0.01,
        hours_to_threshold=40.0,
        predicted_crossing_at=datetime.now(
            timezone.utc
        ),
        confidence=0.80,
    )
    decision = decide_intervention(
        prediction
    )

    assert decision is not None
    assert (
        decision.status
        == InterventionStatus.MONITOR
    )

#-5-
def test_intervention_returns_none_without_prediction():
    decision = decide_intervention(
        None
    )

    assert decision is None

#-6-
def test_intervention_rejects_invalid_minimum_confidence():
    with pytest.raises(
        ValueError,
        match=(
            "Minimum confidence must be "
            "between 0 and 1."
        ),
    ):
        decide_intervention(
            None,
            minimum_confidence=1.20,
        )

#-7-

from datetime import (
    datetime,
    timezone,
)

import pytest
from pydantic import ValidationError

from app.models import (
    ObservationCategory,
    ThresholdPrediction,
)
from app.services import decide_intervention

#-tests-

#-1-
def test_threshold_prediction_can_be_created():
    now = datetime.now(timezone.utc)

    prediction = ThresholdPrediction(
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        current_value=0.60,
        threshold=0.90,
        rate_per_hour=0.10,
        hours_to_threshold=3.0,
        predicted_crossing_at=now,
        confidence=0.90,
    )

    assert prediction.location == "kitchen"
    assert prediction.current_value == 0.60
    assert prediction.threshold == 0.90
    assert prediction.hours_to_threshold == 3.0
    assert prediction.confidence == 0.90

#-2-
def test_threshold_prediction_rejects_invalid_threshold():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        ThresholdPrediction(
            location="kitchen",
            category=ObservationCategory.DISH_LOAD,
            current_value=0.60,
            threshold=1.20,
            rate_per_hour=0.10,
            hours_to_threshold=3.0,
            predicted_crossing_at=now,
            confidence=0.90,
        )

#-3-
def test_threshold_prediction_rejects_negative_hours():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        ThresholdPrediction(
            location="kitchen",
            category=ObservationCategory.DISH_LOAD,
            current_value=0.60,
            threshold=0.90,
            rate_per_hour=0.10,
            hours_to_threshold=-1.0,
            predicted_crossing_at=now,
            confidence=0.90,
        )

#-4-
def test_intervention_rejects_invalid_planning_window():
    with pytest.raises(
        ValueError,
        match=(
            "Planning window must be "
            "greater than zero."
        ),
    ):
        decide_intervention(
            None,
            planning_window_hours=0.0,
        )
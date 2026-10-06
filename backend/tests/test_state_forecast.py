from datetime import (
    datetime,
    timezone,
)

import pytest
from pydantic import ValidationError

from app.models import (
    ObservationCategory,
    StateForecast,
    TrendDirection,
)

#-tests-

#-1-
def test_state_forecast_can_be_created():
    now = datetime.now(
        timezone.utc
    )

    forecast = StateForecast(
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        current_value=0.60,
        predicted_value=0.75,
        rate_per_hour=0.075,
        forecast_hours=2.0,
        predicted_at=now,
        trend=TrendDirection.RISING,
        confidence=0.90,
    )

    assert forecast.location == "kitchen"
    assert forecast.current_value == 0.60
    assert forecast.predicted_value == 0.75
    assert forecast.rate_per_hour == 0.075
    assert forecast.forecast_hours == 2.0

#-2-
def test_state_forecast_rejects_invalid_predicted_value():
    now = datetime.now(
        timezone.utc
    )
    with pytest.raises(ValidationError):
        StateForecast(
            location="kitchen",
            category=ObservationCategory.DISH_LOAD,
            current_value=0.60,
            predicted_value=1.20,
            rate_per_hour=0.10,
            forecast_hours=2.0,
            predicted_at=now,
            trend=TrendDirection.RISING,
            confidence=0.90,
        )

#-3-
def test_state_forecast_rejects_invalid_confidence():
    now = datetime.now(
        timezone.utc
    )
    with pytest.raises(ValidationError):
        StateForecast(
            location="kitchen",
            category=ObservationCategory.DISH_LOAD,
            current_value=0.60,
            predicted_value=0.75,
            rate_per_hour=0.075,
            forecast_hours=2.0,
            predicted_at=now,
            trend=TrendDirection.RISING,
            confidence=1.50,
        )
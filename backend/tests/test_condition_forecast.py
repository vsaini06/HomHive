from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import (
    ConditionForecast,
    ConditionTrend,
    ConditionType,
)


def test_condition_forecast_can_be_created():
    now = datetime.now(timezone.utc)

    forecast = ConditionForecast(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.60,
        predicted_value=0.75,
        rate_per_hour=0.075,
        forecast_hours=2.0,
        predicted_at=now,
        trend=ConditionTrend.RISING,
        confidence=0.90,
    )

    assert forecast.location == "kitchen"
    assert forecast.current_value == 0.60
    assert forecast.predicted_value == 0.75
    assert forecast.rate_per_hour == 0.075
    assert forecast.forecast_hours == 2.0


def test_condition_forecast_rejects_invalid_predicted_value():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        ConditionForecast(
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            current_value=0.60,
            predicted_value=1.20,
            rate_per_hour=0.10,
            forecast_hours=2.0,
            predicted_at=now,
            trend=ConditionTrend.RISING,
            confidence=0.90,
        )


def test_condition_forecast_rejects_invalid_confidence():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        ConditionForecast(
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            current_value=0.60,
            predicted_value=0.75,
            rate_per_hour=0.075,
            forecast_hours=2.0,
            predicted_at=now,
            trend=ConditionTrend.RISING,
            confidence=1.50,
        )

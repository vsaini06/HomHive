from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.models import (
    ConditionSnapshot,
    Observation,
    ConditionType,
    ObservationSource,
    ConditionTrend,
)
from app.services import (
    estimate_hourly_change,
    build_condition_forecast,
    project_condition_level,
    estimate_hours_to_threshold,
    forecast_threshold_crossing,
    estimate_forecast_confidence,
)

#-tests-

#-1-
def test_calculate_positive_rate_per_hour():
    now = datetime.now(timezone.utc)
    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.20,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.50,
        confidence=0.90,
        timestamp=now,
    )
    rate = estimate_hourly_change(
        [
            old_observation,
            new_observation,
        ]
    )

    assert rate == pytest.approx(0.15)

#-2-
def test_calculate_negative_rate_per_hour():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )

    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.40,
        confidence=0.90,
        timestamp=now,
    )
    rate = estimate_hourly_change(
        [
            old_observation,
            new_observation,
        ]
    )

    assert rate == pytest.approx(-0.20)

#-3-
def test_rate_is_zero_with_one_observation():
    now = datetime.now(timezone.utc)

    observation = Observation(
        id="obs_001",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.50,
        confidence=0.90,
        timestamp=now,
    )
    rate = estimate_hourly_change(
        [observation]
    )

    assert rate == 0.0

#-4-
def test_rate_uses_timestamps_not_input_order():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.20,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )

    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.50,
        confidence=0.90,
        timestamp=now,
    )
    rate = estimate_hourly_change(
        [
            new_observation,
            old_observation,
        ]
    )

    assert rate == pytest.approx(0.15)

#-5-
def test_project_condition_level_with_rising_state():
    predicted_value = project_condition_level(
        current_level=0.60,
        hourly_change=0.075,
        hours_ahead=2.0,
    )

    assert predicted_value == pytest.approx(
        0.75
    )

#-6-
def test_project_condition_level_with_falling_state():
    predicted_value = project_condition_level(
        current_level=0.80,
        hourly_change=-0.10,
        hours_ahead=3.0,
    )

    assert predicted_value == pytest.approx(
        0.50
    )

#-7-
def test_project_condition_level_is_clamped_to_one():
    predicted_value = project_condition_level(
        current_level=0.90,
        hourly_change=0.10,
        hours_ahead=3.0,
    )

    assert predicted_value == 1.0

#-8-
def test_project_condition_level_is_clamped_to_zero():
    predicted_value = project_condition_level(
        current_level=0.10,
        hourly_change=-0.10,
        hours_ahead=3.0,
    )

    assert predicted_value == 0.0

#-9-
def test_project_condition_level_rejects_non_positive_forecast_hours():
    with pytest.raises(
        ValueError,
        match=(
            "Forecast hours must be "
            "greater than zero."
        ),
    ):
        project_condition_level(
            current_level=0.50,
            hourly_change=0.10,
            hours_ahead=0.0,
        )

#-10-
def test_build_condition_forecast():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.40,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.60,
        confidence=0.90,
        timestamp=now,
    )
    aggregated_state = ConditionSnapshot(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.60,
        confidence=0.90,
        trend=ConditionTrend.RISING,
        latest_observation=new_observation,
        observation_count=2,
        updated_at=now,
    )
    forecast = build_condition_forecast(
        snapshot=aggregated_state,
        observations=[
            old_observation,
            new_observation,
        ],
        hours_ahead=2.0,
    )

    assert forecast.location == "kitchen"
    assert (
        forecast.category
        == ConditionType.DISH_LOAD
    )
    assert forecast.current_value == 0.60
    assert forecast.rate_per_hour == pytest.approx(
        0.10
    )
    assert forecast.predicted_value == pytest.approx(
        0.80
    )
    assert forecast.forecast_hours == 2.0
    assert forecast.predicted_at == (
        now + timedelta(hours=2)
    )
    assert forecast.trend == ConditionTrend.RISING
    expected_confidence = (
        estimate_forecast_confidence(
             observations=[
                old_observation,
                new_observation,
            ],
            hours_ahead=2.0,
        )
    )
    assert (
        forecast.confidence
        == expected_confidence
    )

#-11-
def test_generate_falling_state_forecast():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="laundry_room",
        category=ConditionType.LAUNDRY_LOAD,
        value=0.80,
        confidence=0.95,
        timestamp=now - timedelta(hours=4),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="laundry_room",
        category=ConditionType.LAUNDRY_LOAD,
        value=0.60,
        confidence=0.95,
        timestamp=now,
    )
    aggregated_state = ConditionSnapshot(
        location="laundry_room",
        category=ConditionType.LAUNDRY_LOAD,
        current_value=0.60,
        confidence=0.95,
        trend=ConditionTrend.FALLING,
        latest_observation=new_observation,
        observation_count=2,
        updated_at=now,
    )
    forecast = build_condition_forecast(
        snapshot=aggregated_state,
        observations=[
            old_observation,
            new_observation,
        ],
        hours_ahead=2.0,
    )

    assert forecast.rate_per_hour == pytest.approx(
        -0.05
    )
    assert forecast.predicted_value == pytest.approx(
        0.50
    )
    assert forecast.trend == ConditionTrend.FALLING

#-12-
def test_estimate_hours_to_threshold():
    hours = estimate_hours_to_threshold(
        current_level=0.60,
        hourly_change=0.10,
        threshold=0.90,
    )

    assert hours == pytest.approx(3.0)

#-13-
def test_hours_to_threshold_is_zero_when_threshold_reached():
    hours = estimate_hours_to_threshold(
        current_level=0.90,
        hourly_change=0.10,
        threshold=0.90,
    )

    assert hours == 0.0

#-14-
def test_hours_to_threshold_is_zero_when_above_threshold():
    hours = estimate_hours_to_threshold(
        current_level=0.95,
        hourly_change=0.10,
        threshold=0.90,
    )

    assert hours == 0.0

#-15-
def test_hours_to_threshold_is_none_when_state_is_stable():
    hours = estimate_hours_to_threshold(
        current_level=0.60,
        hourly_change=0.0,
        threshold=0.90,
    )

    assert hours is None

#-16-
def test_hours_to_threshold_is_none_when_state_is_falling():
    hours = estimate_hours_to_threshold(
        current_level=0.60,
        hourly_change=-0.10,
        threshold=0.90,
    )

    assert hours is None

#-17-
def test_hours_to_threshold_rejects_invalid_threshold():
    with pytest.raises(
        ValueError,
        match="Threshold must be between 0 and 1.",
    ):
        estimate_hours_to_threshold(
            current_level=0.60,
            hourly_change=0.10,
            threshold=1.20,
        )

#-18-
def test_forecast_threshold_crossing():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.40,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )

    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.60,
        confidence=0.90,
        timestamp=now,
    )

    aggregated_state = ConditionSnapshot(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.60,
        confidence=0.90,
        trend=ConditionTrend.RISING,
        latest_observation=new_observation,
        observation_count=2,
        updated_at=now,
    )

    prediction = forecast_threshold_crossing(
        snapshot=aggregated_state,
        observations=[
            old_observation,
            new_observation,
        ],
        threshold=0.90,
    )

    assert prediction is not None
    assert prediction.hours_to_threshold == pytest.approx(
        3.0
    )
    assert prediction.predicted_crossing_at == (
        now + timedelta(hours=3)
    )
    assert prediction.threshold == 0.90
    expected_confidence = (
        estimate_forecast_confidence(
            observations=[
                old_observation,
                new_observation,
            ],
            hours_ahead=3.0,
        )
    )
    assert (
        prediction.confidence
        == expected_confidence
    )

#-19-
def test_forecast_threshold_crossing_returns_none_when_moving_away():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.70,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.60,
        confidence=0.90,
        timestamp=now,
    )
    aggregated_state = ConditionSnapshot(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.60,
        confidence=0.90,
        trend=ConditionTrend.FALLING,
        latest_observation=new_observation,
        observation_count=2,
        updated_at=now,
    )
    prediction = forecast_threshold_crossing(
        snapshot=aggregated_state,
        observations=[
            old_observation,
            new_observation,
        ],
        threshold=0.90,
    )

    assert prediction is None

#-20-
def test_forecast_confidence_increases_with_more_observations():
    now = datetime.now(timezone.utc)

    observations = [
        Observation(
            id=f"obs_{index}",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            value=0.50,
            confidence=0.90,
            timestamp=now - timedelta(hours=index),
        )
        for index in range(5)
    ]

    low_evidence_confidence = (
        estimate_forecast_confidence(
            observations=observations[:2],
            hours_ahead=2.0,
        )
    )

    high_evidence_confidence = (
        estimate_forecast_confidence(
            observations=observations,
            hours_ahead=2.0,
        )
    )

    assert (
        high_evidence_confidence
        > low_evidence_confidence
    )

#-21-
def test_forecast_confidence_decreases_with_distance():
    now = datetime.now(timezone.utc)

    observations = [
        Observation(
            id=f"obs_{index}",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            value=0.50,
            confidence=0.90,
            timestamp=now - timedelta(hours=index),
        )
        for index in range(5)
    ]

    short_forecast_confidence = (
        estimate_forecast_confidence(
            observations=observations,
            hours_ahead=2.0,
        )
    )

    long_forecast_confidence = (
        estimate_forecast_confidence(
            observations=observations,
            hours_ahead=24.0,
        )
    )

    assert (
        short_forecast_confidence
        > long_forecast_confidence
    )

#-22-
def test_forecast_confidence_is_zero_without_observations():
    confidence = estimate_forecast_confidence(
        observations=[],
        hours_ahead=2.0,
    )

    assert confidence == 0.0

#-23-
def test_forecast_confidence_rejects_negative_hours():
    with pytest.raises(
        ValueError,
        match="Forecast hours cannot be negative.",
    ):
        estimate_forecast_confidence(
            observations=[],
            hours_ahead=-1.0,
        )

#-24-
def test_nearer_threshold_crossing_has_higher_confidence():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.40,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )

    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.60,
        confidence=0.90,
        timestamp=now,
    )

    aggregated_state = ConditionSnapshot(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.60,
        confidence=0.90,
        trend=ConditionTrend.RISING,
        latest_observation=new_observation,
        observation_count=2,
        updated_at=now,
    )

    observations = [
        old_observation,
        new_observation,
    ]

    near_prediction = forecast_threshold_crossing(
        snapshot=aggregated_state,
        observations=observations,
        threshold=0.70,
    )

    far_prediction = forecast_threshold_crossing(
        snapshot=aggregated_state,
        observations=observations,
        threshold=0.90,
    )

    assert near_prediction is not None
    assert far_prediction is not None

    assert (
        near_prediction.hours_to_threshold
        < far_prediction.hours_to_threshold
    )

    assert (
        near_prediction.confidence
        > far_prediction.confidence
    )

#-26-
def test_threshold_prediction_handles_already_reached_threshold():
    now = datetime.now(timezone.utc)

    observation = Observation(
        id="obs_current",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.95,
        confidence=0.90,
        timestamp=now,
    )

    aggregated_state = ConditionSnapshot(
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        current_value=0.95,
        confidence=0.90,
        trend=ConditionTrend.UNKNOWN,
        latest_observation=observation,
        observation_count=1,
        updated_at=now,
    )

    prediction = forecast_threshold_crossing(
        snapshot=aggregated_state,
        observations=[observation],
        threshold=0.90,
    )

    assert prediction is not None
    assert prediction.hours_to_threshold == 0.0
    assert prediction.predicted_crossing_at == now
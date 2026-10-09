from datetime import timedelta

from app.models import (
    ConditionForecast,
    ConditionSnapshot,
    Observation,
    ThresholdCrossing,
)


def estimate_hourly_change(
    observations: list[Observation],
) -> float:
    """Estimate how quickly a condition changed between the first and latest reading."""

    if len(observations) < 2:
        return 0.0

    ordered_observations = sorted(
        observations,
        key=lambda observation: observation.timestamp,
    )

    first_observation = ordered_observations[0]
    latest_observation = ordered_observations[-1]

    elapsed_seconds = (
        latest_observation.timestamp
        - first_observation.timestamp
    ).total_seconds()

    # Two readings at the same timestamp cannot tell us how quickly something changed.
    if elapsed_seconds <= 0:
        return 0.0

    elapsed_hours = elapsed_seconds / 3600

    condition_change = (
        latest_observation.value
        - first_observation.value
    )

    return condition_change / elapsed_hours


def project_condition_level(
    current_level: float,
    hourly_change: float,
    hours_ahead: float,
) -> float:
    """Project a condition forward while keeping it inside HomHive's 0-1 scale."""

    if hours_ahead <= 0:
        raise ValueError(
            "Forecast hours must be greater than zero."
        )

    projected_level = (
        current_level
        + hourly_change * hours_ahead
    )

    return max(
        0.0,
        min(
            1.0,
            projected_level,
        ),
    )


def estimate_forecast_confidence(
    observations: list[Observation],
    hours_ahead: float,
) -> float:
    """Estimate how much confidence to place in a forecast at this distance."""

    if hours_ahead < 0:
        raise ValueError(
            "Forecast hours cannot be negative."
        )

    if not observations:
        return 0.0

    average_observation_confidence = (
        sum(
            observation.confidence
            for observation in observations
        )
        / len(observations)
    )

    evidence_strength = min(
        1.0,
        len(observations) / 5.0,
    )

    # Predictions become less trustworthy as we look farther into the future.
    forecast_distance = (
        1.0
        / (
            1.0
            + hours_ahead / 24.0
        )
    )

    forecast_confidence = (
        average_observation_confidence
        * evidence_strength
        * forecast_distance
    )

    return round(
        forecast_confidence,
        4,
    )


def build_condition_forecast(
    snapshot: ConditionSnapshot,
    observations: list[Observation],
    hours_ahead: float,
) -> ConditionForecast:
    """Project the current condition snapshot forward by a chosen number of hours."""

    if hours_ahead <= 0:
        raise ValueError(
            "Forecast hours must be greater than zero."
        )

    hourly_change = estimate_hourly_change(
        observations
    )

    projected_level = project_condition_level(
        current_level=snapshot.current_value,
        hourly_change=hourly_change,
        hours_ahead=hours_ahead,
    )

    predicted_at = (
        snapshot.updated_at
        + timedelta(
            hours=hours_ahead
        )
    )

    return ConditionForecast(
        location=snapshot.location,
        category=snapshot.category,
        current_value=snapshot.current_value,
        predicted_value=projected_level,
        rate_per_hour=hourly_change,
        forecast_hours=hours_ahead,
        predicted_at=predicted_at,
        trend=snapshot.trend,
        confidence=estimate_forecast_confidence(
            observations=observations,
            hours_ahead=hours_ahead,
        ),
    )


def estimate_hours_to_threshold(
    current_level: float,
    hourly_change: float,
    threshold: float,
) -> float | None:
    """Estimate when a rising condition will reach a configured threshold."""

    if not 0.0 <= threshold <= 1.0:
        raise ValueError(
            "Threshold must be between 0 and 1."
        )

    if current_level >= threshold:
        return 0.0

    # A flat or improving condition is not moving toward an upper threshold.
    if hourly_change <= 0:
        return None

    return (
        threshold - current_level
    ) / hourly_change


def forecast_threshold_crossing(
    snapshot: ConditionSnapshot,
    observations: list[Observation],
    threshold: float,
) -> ThresholdCrossing | None:
    """Forecast when a household condition is expected to reach a threshold."""

    hourly_change = estimate_hourly_change(
        observations
    )

    hours_to_threshold = (
        estimate_hours_to_threshold(
            current_level=snapshot.current_value,
            hourly_change=hourly_change,
            threshold=threshold,
        )
    )

    if hours_to_threshold is None:
        return None

    crossing_time = (
        snapshot.updated_at
        + timedelta(
            hours=hours_to_threshold
        )
    )

    return ThresholdCrossing(
        location=snapshot.location,
        category=snapshot.category,
        current_value=snapshot.current_value,
        threshold=threshold,
        rate_per_hour=hourly_change,
        hours_to_threshold=hours_to_threshold,
        predicted_crossing_at=crossing_time,
        confidence=estimate_forecast_confidence(
            observations=observations,
            hours_ahead=hours_to_threshold,
        ),
    )

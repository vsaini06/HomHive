from datetime import timedelta

from app.models import (
    AggregatedState,
    Observation,
    StateForecast,
    ThresholdPrediction,
)


def calculate_rate_per_hour(
    observations: list[Observation],
) -> float:
    if len(observations) < 2:
        return 0.0

    ordered_observations = sorted(
        observations,
        key=lambda observation: observation.timestamp,
    )

    oldest_observation = ordered_observations[0]
    newest_observation = ordered_observations[-1]

    elapsed_seconds = (
        newest_observation.timestamp
        - oldest_observation.timestamp
    ).total_seconds()

    if elapsed_seconds <= 0:
        return 0.0

    elapsed_hours = (
        elapsed_seconds / 3600
    )

    value_change = (
        newest_observation.value
        - oldest_observation.value
    )

    return value_change / elapsed_hours

def predict_value(
    current_value: float,
    rate_per_hour: float,
    forecast_hours: float,
) -> float:
    if forecast_hours <= 0:
        raise ValueError(
            "Forecast hours must be greater than zero."
        )
    predicted_value = (
        current_value
        + rate_per_hour * forecast_hours
    )
    return max(
        0.0,
        min(1.0, predicted_value),
    )

def generate_state_forecast(
    aggregated_state: AggregatedState,
    observations: list[Observation],
    forecast_hours: float,
) -> StateForecast:
    if forecast_hours <= 0:
        raise ValueError(
            "Forecast hours must be greater than zero."
        )

    rate_per_hour = calculate_rate_per_hour(
        observations
    )
    predicted_value = predict_value(
        current_value=aggregated_state.current_value,
        rate_per_hour=rate_per_hour,
        forecast_hours=forecast_hours,
    )
    predicted_at = (
        aggregated_state.updated_at
        + timedelta(hours=forecast_hours)
    )

    return StateForecast(
        location=aggregated_state.location,
        category=aggregated_state.category,
        current_value=aggregated_state.current_value,
        predicted_value=predicted_value,
        rate_per_hour=rate_per_hour,
        forecast_hours=forecast_hours,
        predicted_at=predicted_at,
        trend=aggregated_state.trend,
        confidence=calculate_forecast_confidence(
            observations=observations,
            forecast_hours=forecast_hours,
        ),
    )

def calculate_hours_to_threshold(
    current_value: float,
    rate_per_hour: float,
    threshold: float,
) -> float | None:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(
            "Threshold must be between 0 and 1."
        )
    if current_value >= threshold:
        return 0.0
    if rate_per_hour <= 0:
        return None
    return (
        threshold - current_value
    ) / rate_per_hour


def generate_threshold_prediction(
    aggregated_state: AggregatedState,
    observations: list[Observation],
    threshold: float,
) -> ThresholdPrediction | None:
    rate_per_hour = calculate_rate_per_hour(
        observations
    )

    hours_to_threshold = (
        calculate_hours_to_threshold(
            current_value=aggregated_state.current_value,
            rate_per_hour=rate_per_hour,
            threshold=threshold,
        )
    )

    if hours_to_threshold is None:
        return None

    predicted_crossing_at = (
        aggregated_state.updated_at
        + timedelta(
            hours=hours_to_threshold
        )
    )

    return ThresholdPrediction(
        location=aggregated_state.location,
        category=aggregated_state.category,
        current_value=aggregated_state.current_value,
        threshold=threshold,
        rate_per_hour=rate_per_hour,
        hours_to_threshold=hours_to_threshold,
        predicted_crossing_at=predicted_crossing_at,
        confidence=calculate_forecast_confidence(
            observations=observations,
            forecast_hours=hours_to_threshold,
        ),
    )

def calculate_forecast_confidence(
    observations: list[Observation],
    forecast_hours: float,
) -> float:
    if forecast_hours < 0:
        raise ValueError(
            "Forecast hours cannot be negative."
        )

    if not observations:
        return 0.0

    if forecast_hours < 0:
        raise ValueError(
            "Forecast hours cannot be negative."
        )
    average_confidence = sum(
        observation.confidence
        for observation in observations
    ) / len(observations)
    evidence_factor = min(
        1.0,
        len(observations) / 5.0,
    )
    distance_factor = (
        1.0 / (1.0 + forecast_hours / 24.0)
    )
    confidence = (
        average_confidence
        * evidence_factor
        * distance_factor
    )

    return round(confidence, 4)
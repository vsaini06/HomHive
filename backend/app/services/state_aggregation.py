from datetime import datetime

from app.models import (
    AggregatedState,
    HouseholdState,
    Observation,
    TrendDirection,
)


def calculate_recency_weight(
    observation_time: datetime,
    reference_time: datetime,
) -> float:
    age_seconds = max(
        0.0,
        (reference_time - observation_time).total_seconds(),
    )
    age_hours = age_seconds / 3600
    return 1 / (1 + age_hours)


def calculate_observation_weight(
    observation: Observation,
    reference_time: datetime,
) -> float:
    recency_weight = calculate_recency_weight(
        observation.timestamp,
        reference_time,
    )
    return observation.confidence * recency_weight


def aggregate_observations(
    observations: list[Observation],
) -> AggregatedState:
    if not observations:
        raise ValueError(
            "Cannot aggregate an empty observation list."
        )

    first_observation = observations[0]

    for observation in observations:
        if observation.location != first_observation.location:
            raise ValueError(
                "All observations must have the same location."
            )
        if observation.category != first_observation.category:
            raise ValueError(
                "All observations must have the same category."
            )

    reference_time = max(
        observation.timestamp
        for observation in observations
    )
    weighted_value_sum = 0.0
    total_weight = 0.0

    for observation in observations:
        weight = calculate_observation_weight(
            observation,
            reference_time,
        )
        weighted_value_sum += observation.value * weight
        total_weight += weight

    if total_weight == 0:
        raise ValueError(
            "Cannot aggregate observations with zero total weight."
        )

    current_value = (
        weighted_value_sum
        / total_weight
    )

    latest_observation = max(
        observations,
        key=lambda observation: observation.timestamp,
    )

    trend = calculate_trend(
        observations
    )

    return AggregatedState(
        location=first_observation.location,
        category=first_observation.category,
        current_value=round(current_value, 4),
        confidence=round(
            max(
                observation.confidence
                for observation in observations
            ),
            4,
        ),
        trend=trend,
        latest_observation=latest_observation,
        observation_count=len(observations),
        updated_at=reference_time,
    )



def aggregate_household_state(
    household_state: HouseholdState,
) -> dict[str, AggregatedState]:
    grouped_observations: dict[
        str,
        list[Observation],
    ] = {}

    for observation in household_state.observation_history:
        state_key = (
            f"{observation.location}:"
            f"{observation.category.value}"
        )

        grouped_observations.setdefault(
            state_key,
            [],
        ).append(observation)

    aggregated_states: dict[
        str,
        AggregatedState,
    ] = {}

    for state_key, observations in grouped_observations.items():
        aggregated_states[state_key] = (
            aggregate_observations(
                observations
            )
        )
    return aggregated_states


def calculate_trend(
    observations: list[Observation],
    stable_threshold: float = 0.05,
) -> TrendDirection:
    if len(observations) < 2:
        return TrendDirection.UNKNOWN

    ordered_observations = sorted(
        observations,
        key=lambda observation: observation.timestamp,
    )

    oldest_observation = ordered_observations[0]
    newest_observation = ordered_observations[-1]

    change = (
        newest_observation.value
        - oldest_observation.value
    )

    if round(abs(change), 4) <= stable_threshold:
        return TrendDirection.STABLE
    if change > 0:
        return TrendDirection.RISING

    return TrendDirection.FALLING
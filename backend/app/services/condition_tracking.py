from datetime import datetime

from app.models import (
    ConditionSnapshot,
    ConditionTrend,
    HouseholdState,
    Observation,
)


def recency_weight(
    observed_at: datetime,
    compared_at: datetime,
) -> float:
    """Give newer observations more influence than older ones."""

    age_seconds = max(
        0.0,
        (compared_at - observed_at).total_seconds(),
    )
    age_hours = age_seconds / 3600

    return 1 / (1 + age_hours)


def observation_weight(
    observation: Observation,
    compared_at: datetime,
) -> float:
    """Combine observation confidence with how recent the evidence is."""

    age_weight = recency_weight(
        observed_at=observation.timestamp,
        compared_at=compared_at,
    )

    return observation.confidence * age_weight


def detect_condition_trend(
    observations: list[Observation],
    stable_change: float = 0.05,
) -> ConditionTrend:
    """Describe whether a condition is rising, falling, or staying roughly stable."""

    if len(observations) < 2:
        return ConditionTrend.UNKNOWN

    ordered_observations = sorted(
        observations,
        key=lambda observation: observation.timestamp,
    )

    first_reading = ordered_observations[0]
    latest_reading = ordered_observations[-1]

    level_change = (
        latest_reading.value
        - first_reading.value
    )

    # Tiny changes are treated as noise rather than a meaningful trend.
    if round(abs(level_change), 4) <= stable_change:
        return ConditionTrend.STABLE

    if level_change > 0:
        return ConditionTrend.RISING

    return ConditionTrend.FALLING


def build_condition_snapshot(
    observations: list[Observation],
) -> ConditionSnapshot:
    """Build HomHive's current view of one household condition."""

    if not observations:
        raise ValueError(
            "Cannot build a condition snapshot from an empty observation list."
        )

    reference_observation = observations[0]

    for observation in observations:
        if observation.location != reference_observation.location:
            raise ValueError(
                "All observations must have the same location."
            )

        if observation.category != reference_observation.category:
            raise ValueError(
                "All observations must have the same category."
            )

    latest_timestamp = max(
        observation.timestamp
        for observation in observations
    )

    weighted_level_total = 0.0
    weight_total = 0.0

    for observation in observations:
        weight = observation_weight(
            observation=observation,
            compared_at=latest_timestamp,
        )

        weighted_level_total += (
            observation.value * weight
        )
        weight_total += weight

    if weight_total == 0:
        raise ValueError(
            "Cannot build a condition snapshot with zero total weight."
        )

    current_level = (
        weighted_level_total
        / weight_total
    )

    latest_observation = max(
        observations,
        key=lambda observation: observation.timestamp,
    )

    trend = detect_condition_trend(
        observations
    )

    # We keep confidence conservative for now instead of increasing it
    # simply because several observations happen to exist.
    snapshot_confidence = max(
        observation.confidence
        for observation in observations
    )

    return ConditionSnapshot(
        location=reference_observation.location,
        category=reference_observation.category,
        current_value=round(
            current_level,
            4,
        ),
        confidence=round(
            snapshot_confidence,
            4,
        ),
        trend=trend,
        latest_observation=latest_observation,
        observation_count=len(observations),
        updated_at=latest_timestamp,
    )


def build_household_condition_snapshots(
    household_state: HouseholdState,
) -> dict[str, ConditionSnapshot]:
    """Build one current snapshot for every tracked condition in the home."""
    observations_by_condition: dict[
        str,
        list[Observation],
    ] = {}

    for observation in household_state.observation_history:
        condition_key = observation.state_key()

        observations_by_condition.setdefault(
            condition_key,
            [],
        ).append(observation)

    snapshots: dict[
        str,
        ConditionSnapshot,
    ] = {}

    for (
        condition_key,
        observations,
    ) in observations_by_condition.items():
        snapshots[condition_key] = (
            build_condition_snapshot(
                observations
            )
        )

    return snapshots
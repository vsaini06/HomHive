from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    HouseholdState,
    Observation,
    ObservationCategory,
    ObservationSource,
    TrendDirection,
)

from app.services.state_aggregation import (
    aggregate_household_state,
    aggregate_observations,
    calculate_observation_weight,
    calculate_recency_weight,
    calculate_trend,
)

#-tests-

#-1-
def test_current_observation_has_full_recency_weight():
    now = datetime.now(timezone.utc)

    weight = calculate_recency_weight(
        observation_time=now,
        reference_time=now,
    )
    assert weight == 1.0

#-2-
def test_older_observation_has_lower_recency_weight():
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=2)

    old_weight = calculate_recency_weight(
        observation_time=old_time,
        reference_time=now,
    )
    new_weight = calculate_recency_weight(
        observation_time=now,
        reference_time=now,
    )
    assert old_weight < new_weight

#-3-
def test_higher_confidence_produces_higher_weight():
    now = datetime.now(timezone.utc)

    high_confidence = Observation(
        id="obs_high",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )
    low_confidence = Observation(
        id="obs_low",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.30,
        confidence=0.20,
        timestamp=now,
    )

    high_weight = calculate_observation_weight(
        high_confidence,
        now,
    )
    low_weight = calculate_observation_weight(
        low_confidence,
        now,
    )
    assert high_weight > low_weight

#-4-
def test_low_confidence_new_observation_does_not_dominate_state():
    now = datetime.now(timezone.utc)

    strong_old_observation = Observation(
        id="obs_strong",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.95,
        timestamp=now - timedelta(minutes=5),
    )
    weak_new_observation = Observation(
        id="obs_weak",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.30,
        confidence=0.20,
        timestamp=now,
    )

    result = aggregate_observations(
        [
            strong_old_observation,
            weak_new_observation,
        ]
    )
    assert result.current_value > 0.60
    assert result.latest_observation.id == "obs_weak"
    assert result.observation_count == 2

#-5-
def test_strong_new_observation_can_shift_state():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.20,
        confidence=0.95,
        timestamp=now,
    )

    result = aggregate_observations(
        [
            old_observation,
            new_observation,
        ]
    )
    assert result.current_value < 0.50

#-6-
def test_cannot_aggregate_different_locations():
    now = datetime.now(timezone.utc)

    kitchen = Observation(
        id="obs_kitchen",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )
    dining_room = Observation(
        id="obs_dining",
        source=ObservationSource.PHOTO,
        location="dining_room",
        category=ObservationCategory.DISH_LOAD,
        value=0.70,
        confidence=0.90,
        timestamp=now,
    )

    with pytest.raises(
        ValueError,
        match="same location",
    ):
        aggregate_observations(
            [kitchen, dining_room]
        )

#-7-
def test_cannot_aggregate_different_categories():
    now = datetime.now(timezone.utc)

    dishes = Observation(
        id="obs_dishes",
        source=ObservationSource.PHOTO,
        location="utility_room",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )
    laundry = Observation(
        id="obs_laundry",
        source=ObservationSource.PHOTO,
        location="utility_room",
        category=ObservationCategory.LAUNDRY_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )

    with pytest.raises(
        ValueError,
        match="same category",
    ):
        aggregate_observations(
            [dishes, laundry]
        )

#-8-
def test_cannot_aggregate_empty_observation_list():
    with pytest.raises(
        ValueError,
        match="empty observation list",
    ):
        aggregate_observations([])

#-9-
def test_aggregate_household_state_groups_observations():
    now = datetime.now(timezone.utc)

    state = HouseholdState(
        id="home_001"
    )

    observations = [
        Observation(
            id="dish_1",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ObservationCategory.DISH_LOAD,
            value=0.80,
            confidence=0.90,
            timestamp=now - timedelta(minutes=10),
        ),
        Observation(
            id="dish_2",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ObservationCategory.DISH_LOAD,
            value=0.70,
            confidence=0.95,
            timestamp=now,
        ),
        Observation(
            id="laundry_1",
            source=ObservationSource.PHOTO,
            location="laundry_room",
            category=ObservationCategory.LAUNDRY_LOAD,
            value=0.85,
            confidence=0.90,
            timestamp=now,
        ),
    ]

    for observation in observations:
        state.add_observation(observation)

    aggregated_states = aggregate_household_state(
        state
    )

    assert len(aggregated_states) == 2
    assert (
        "kitchen:dish_load"
        in aggregated_states
    )
    assert (
        "laundry_room:laundry_load"
        in aggregated_states
    )
    assert (
        aggregated_states[
            "kitchen:dish_load"
        ].observation_count
        == 2
    )
    assert (
        aggregated_states[
            "laundry_room:laundry_load"
        ].observation_count
        == 1
    )

#-10-
def test_same_category_in_different_locations_stays_separate():
    now = datetime.now(timezone.utc)

    state = HouseholdState(
        id="home_001"
    )
    kitchen = Observation(
        id="kitchen_dishes",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )
    dining_room = Observation(
        id="dining_dishes",
        source=ObservationSource.PHOTO,
        location="dining_room",
        category=ObservationCategory.DISH_LOAD,
        value=0.40,
        confidence=0.90,
        timestamp=now,
    )

    state.add_observation(kitchen)
    state.add_observation(dining_room)

    aggregated_states = aggregate_household_state(
        state
    )

    assert len(aggregated_states) == 2
    assert (
        "kitchen:dish_load"
        in aggregated_states
    )
    assert (
        "dining_room:dish_load"
        in aggregated_states
    )

#-11-
def test_empty_household_state_returns_empty_aggregation():
    state = HouseholdState(
        id="home_001"
    )

    aggregated_states = aggregate_household_state(
        state
    )

    assert aggregated_states == {}

#-12-
def test_household_aggregation_uses_temporal_aggregation():
    now = datetime.now(timezone.utc)

    state = HouseholdState(
        id="home_001"
    )

    strong_old = Observation(
        id="strong_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.95,
        timestamp=now - timedelta(minutes=5),
    )

    weak_new = Observation(
        id="weak_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.30,
        confidence=0.20,
        timestamp=now,
    )

    state.add_observation(strong_old)
    state.add_observation(weak_new)

    aggregated_states = aggregate_household_state(
        state
    )

    kitchen_state = aggregated_states[
        "kitchen:dish_load"
    ]

    assert kitchen_state.observation_count == 2
    assert kitchen_state.latest_observation.id == "weak_new"
    assert kitchen_state.current_value > 0.60

#-13-
def test_trend_is_unknown_with_one_observation():
    now = datetime.now(timezone.utc)

    observation = Observation(
        id="obs_1",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.60,
        confidence=0.90,
        timestamp=now,
    )

    trend = calculate_trend(
        [observation]
    )

    assert trend == TrendDirection.UNKNOWN

#-14-
def test_trend_is_rising():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.30,
        confidence=0.90,
        timestamp=now - timedelta(hours=1),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.70,
        confidence=0.90,
        timestamp=now,
    )

    trend = calculate_trend(
        [
            old_observation,
            new_observation,
        ]
    )

    assert trend == TrendDirection.RISING

#-15-
def test_trend_is_falling():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now - timedelta(hours=1),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.30,
        confidence=0.90,
        timestamp=now,
    )

    trend = calculate_trend(
        [
            old_observation,
            new_observation,
        ]
    )

    assert trend == TrendDirection.FALLING

#-16-
def test_small_change_is_stable():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.50,
        confidence=0.90,
        timestamp=now - timedelta(hours=1),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.53,
        confidence=0.90,
        timestamp=now,
    )

    trend = calculate_trend(
        [
            old_observation,
            new_observation,
        ]
    )

    assert trend == TrendDirection.STABLE

#-17-
def test_trend_uses_timestamps_not_input_order():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.20,
        confidence=0.90,
        timestamp=now - timedelta(hours=2),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )

    trend = calculate_trend(
        [
            new_observation,
            old_observation,
        ]
    )

    assert trend == TrendDirection.RISING

#-18-
def test_change_at_stable_threshold_is_stable():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.50,
        confidence=0.90,
        timestamp=now - timedelta(hours=1),
    )
    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ObservationCategory.DISH_LOAD,
        value=0.55,
        confidence=0.90,
        timestamp=now,
    )

    trend = calculate_trend(
        [
            old_observation,
            new_observation,
        ]
    )

    assert trend == TrendDirection.STABLE
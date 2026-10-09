from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    ConditionTrend,
    ConditionType,
    HouseholdState,
    Observation,
    ObservationSource,
)

from app.services.condition_tracking import (
    build_condition_snapshot,
    build_household_condition_snapshots,
    detect_condition_trend,
    observation_weight,
    recency_weight,
)


def test_current_observation_has_full_recency_weight():
    now = datetime.now(timezone.utc)

    weight = recency_weight(
        observed_at=now,
        compared_at=now,
    )

    assert weight == 1.0


def test_older_observation_has_lower_recency_weight():
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=2)

    old_weight = recency_weight(
        observed_at=old_time,
        compared_at=now,
    )
    new_weight = recency_weight(
        observed_at=now,
        compared_at=now,
    )

    assert old_weight < new_weight


def test_higher_confidence_produces_higher_observation_weight():
    now = datetime.now(timezone.utc)

    high_confidence_observation = Observation(
        id="obs_high",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )

    low_confidence_observation = Observation(
        id="obs_low",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.30,
        confidence=0.20,
        timestamp=now,
    )

    high_weight = observation_weight(
        observation=high_confidence_observation,
        compared_at=now,
    )
    low_weight = observation_weight(
        observation=low_confidence_observation,
        compared_at=now,
    )

    assert high_weight > low_weight


def test_low_confidence_new_observation_does_not_dominate_snapshot():
    now = datetime.now(timezone.utc)

    strong_old_observation = Observation(
        id="obs_strong",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.80,
        confidence=0.95,
        timestamp=now - timedelta(minutes=5),
    )

    weak_new_observation = Observation(
        id="obs_weak",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.30,
        confidence=0.20,
        timestamp=now,
    )

    snapshot = build_condition_snapshot(
        [
            strong_old_observation,
            weak_new_observation,
        ]
    )

    assert snapshot.current_value > 0.60
    assert snapshot.latest_observation.id == "obs_weak"
    assert snapshot.observation_count == 2


def test_strong_new_observation_can_shift_snapshot():
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
        value=0.20,
        confidence=0.95,
        timestamp=now,
    )

    snapshot = build_condition_snapshot(
        [
            old_observation,
            new_observation,
        ]
    )

    assert snapshot.current_value < 0.50


def test_snapshot_rejects_observations_from_different_locations():
    now = datetime.now(timezone.utc)

    kitchen_observation = Observation(
        id="obs_kitchen",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )

    dining_room_observation = Observation(
        id="obs_dining",
        source=ObservationSource.PHOTO,
        location="dining_room",
        category=ConditionType.DISH_LOAD,
        value=0.70,
        confidence=0.90,
        timestamp=now,
    )

    with pytest.raises(
        ValueError,
        match="same location",
    ):
        build_condition_snapshot(
            [
                kitchen_observation,
                dining_room_observation,
            ]
        )


def test_snapshot_rejects_observations_from_different_condition_types():
    now = datetime.now(timezone.utc)

    dish_observation = Observation(
        id="obs_dishes",
        source=ObservationSource.PHOTO,
        location="utility_room",
        category=ConditionType.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )

    laundry_observation = Observation(
        id="obs_laundry",
        source=ObservationSource.PHOTO,
        location="utility_room",
        category=ConditionType.LAUNDRY_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )

    with pytest.raises(
        ValueError,
        match="same category",
    ):
        build_condition_snapshot(
            [
                dish_observation,
                laundry_observation,
            ]
        )


def test_snapshot_rejects_empty_observation_list():
    with pytest.raises(
        ValueError,
        match="empty observation list",
    ):
        build_condition_snapshot([])


def test_household_snapshot_builder_groups_related_observations():
    now = datetime.now(timezone.utc)
    state = HouseholdState(id="home_001")

    observations = [
        Observation(
            id="dish_1",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            value=0.80,
            confidence=0.90,
            timestamp=now - timedelta(minutes=10),
        ),
        Observation(
            id="dish_2",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            value=0.70,
            confidence=0.95,
            timestamp=now,
        ),
        Observation(
            id="laundry_1",
            source=ObservationSource.PHOTO,
            location="laundry_room",
            category=ConditionType.LAUNDRY_LOAD,
            value=0.85,
            confidence=0.90,
            timestamp=now,
        ),
    ]

    for observation in observations:
        state.add_observation(observation)

    snapshots = build_household_condition_snapshots(
        state
    )

    assert len(snapshots) == 2
    assert "kitchen:dish_load" in snapshots
    assert "laundry_room:laundry_load" in snapshots
    assert snapshots["kitchen:dish_load"].observation_count == 2
    assert snapshots["laundry_room:laundry_load"].observation_count == 1


def test_same_condition_in_different_locations_stays_separate():
    now = datetime.now(timezone.utc)
    state = HouseholdState(id="home_001")

    kitchen_observation = Observation(
        id="kitchen_dishes",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )

    dining_room_observation = Observation(
        id="dining_dishes",
        source=ObservationSource.PHOTO,
        location="dining_room",
        category=ConditionType.DISH_LOAD,
        value=0.40,
        confidence=0.90,
        timestamp=now,
    )

    state.add_observation(kitchen_observation)
    state.add_observation(dining_room_observation)

    snapshots = build_household_condition_snapshots(
        state
    )

    assert len(snapshots) == 2
    assert "kitchen:dish_load" in snapshots
    assert "dining_room:dish_load" in snapshots


def test_empty_household_state_returns_no_condition_snapshots():
    state = HouseholdState(id="home_001")

    snapshots = build_household_condition_snapshots(
        state
    )

    assert snapshots == {}


def test_household_snapshot_builder_uses_weighted_history():
    now = datetime.now(timezone.utc)
    state = HouseholdState(id="home_001")

    strong_old_observation = Observation(
        id="strong_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.80,
        confidence=0.95,
        timestamp=now - timedelta(minutes=5),
    )

    weak_new_observation = Observation(
        id="weak_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.30,
        confidence=0.20,
        timestamp=now,
    )

    state.add_observation(strong_old_observation)
    state.add_observation(weak_new_observation)

    snapshots = build_household_condition_snapshots(
        state
    )

    kitchen_snapshot = snapshots[
        "kitchen:dish_load"
    ]

    assert kitchen_snapshot.observation_count == 2
    assert kitchen_snapshot.latest_observation.id == "weak_new"
    assert kitchen_snapshot.current_value > 0.60


def test_trend_is_unknown_with_one_observation():
    now = datetime.now(timezone.utc)

    observation = Observation(
        id="obs_1",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.60,
        confidence=0.90,
        timestamp=now,
    )

    trend = detect_condition_trend(
        [observation]
    )

    assert trend == ConditionTrend.UNKNOWN


def test_trend_is_rising():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.30,
        confidence=0.90,
        timestamp=now - timedelta(hours=1),
    )

    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.70,
        confidence=0.90,
        timestamp=now,
    )

    trend = detect_condition_trend(
        [
            old_observation,
            new_observation,
        ]
    )

    assert trend == ConditionTrend.RISING


def test_trend_is_falling():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.80,
        confidence=0.90,
        timestamp=now - timedelta(hours=1),
    )

    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.30,
        confidence=0.90,
        timestamp=now,
    )

    trend = detect_condition_trend(
        [
            old_observation,
            new_observation,
        ]
    )

    assert trend == ConditionTrend.FALLING


def test_small_change_is_stable():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.50,
        confidence=0.90,
        timestamp=now - timedelta(hours=1),
    )

    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.53,
        confidence=0.90,
        timestamp=now,
    )

    trend = detect_condition_trend(
        [
            old_observation,
            new_observation,
        ]
    )

    assert trend == ConditionTrend.STABLE


def test_trend_uses_timestamps_not_input_order():
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
        value=0.80,
        confidence=0.90,
        timestamp=now,
    )

    trend = detect_condition_trend(
        [
            new_observation,
            old_observation,
        ]
    )

    assert trend == ConditionTrend.RISING


def test_change_at_stable_threshold_is_stable():
    now = datetime.now(timezone.utc)

    old_observation = Observation(
        id="obs_old",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.50,
        confidence=0.90,
        timestamp=now - timedelta(hours=1),
    )

    new_observation = Observation(
        id="obs_new",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.55,
        confidence=0.90,
        timestamp=now,
    )

    trend = detect_condition_trend(
        [
            old_observation,
            new_observation,
        ]
    )

    assert trend == ConditionTrend.STABLE


def test_state_key_uses_entity_when_available():
    observation = Observation(
        id="obs_001",
        source=ObservationSource.PHOTO,
        location="living_room",
        entity_id="entity_plant_001",
        category=ConditionType.PLANT_CONDITION,
        value=0.40,
        confidence=0.90,
    )

    condition_key = observation.state_key()

    assert (
        condition_key
        == "entity_plant_001:plant_condition"
    )


def test_state_key_uses_location_without_entity():
    observation = Observation(
        id="obs_001",
        source=ObservationSource.PHOTO,
        location="living_room",
        category=ConditionType.PLANT_CONDITION,
        value=0.40,
        confidence=0.90,
    )

    condition_key = observation.state_key()

    assert (
        condition_key
        == "living_room:plant_condition"
    )


def test_different_entities_in_same_location_stay_separate():
    state = HouseholdState(id="home_001")

    first_plant_observation = Observation(
        id="obs_plant_001",
        source=ObservationSource.PHOTO,
        location="living_room",
        entity_id="entity_plant_001",
        category=ConditionType.PLANT_CONDITION,
        value=0.30,
        confidence=0.90,
    )

    second_plant_observation = Observation(
        id="obs_plant_002",
        source=ObservationSource.PHOTO,
        location="living_room",
        entity_id="entity_plant_002",
        category=ConditionType.PLANT_CONDITION,
        value=0.80,
        confidence=0.90,
    )

    state.add_observation(first_plant_observation)
    state.add_observation(second_plant_observation)

    snapshots = build_household_condition_snapshots(
        state
    )

    assert len(snapshots) == 2
    assert (
        "entity_plant_001:plant_condition"
        in snapshots
    )
    assert (
        "entity_plant_002:plant_condition"
        in snapshots
    )

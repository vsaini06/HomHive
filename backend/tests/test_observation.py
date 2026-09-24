import pytest
from pydantic import ValidationError

from app.models import (
    Observation,
    ObservationCategory,
    ObservationSource,
    HouseholdState,
)

#-tests-

#-1-
def test_valid_observation():
    observation = Observation(
        id="obs_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.82,
        confidence=0.91,
    )

    assert observation.id == "obs_001"
    assert observation.location == "kitchen"
    assert observation.value == 0.82
    assert observation.confidence == 0.91

#-2-
def test_observation_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Observation(
            id="obs_002",
            source="photo",
            location="kitchen",
            category="dish_load",
            value=2.0,
            confidence=0.91,
        )

#-3-
def test_observation_rejects_invalid_source():
    with pytest.raises(ValidationError):
        Observation(
            id="obs_003",
            source="random",
            location="kitchen",
            category="dish_load",
            value=0.5,
            confidence=0.91,
        )

#-4-
def test_observation_can_reference_entity():
    observation = Observation(
        id="obs_001",
        source=ObservationSource.PHOTO,
        location="living_room",
        entity_id="entity_plant_001",
        category=ObservationCategory.PLANT_CONDITION,
        value=0.42,
        confidence=0.91,
    )

    assert observation.entity_id == "entity_plant_001"

#-5-
def test_observation_does_not_require_entity():
    observation = Observation(
        id="obs_001",
        source=ObservationSource.PHOTO,
        location="living_room",
        category=ObservationCategory.PLANT_CONDITION,
        value=0.42,
        confidence=0.91,
    )

    assert observation.entity_id is None

#-6-
def test_observation_state_key_uses_entity():
    observation = Observation(
        id="obs_001",
        source=ObservationSource.PHOTO,
        location="living_room",
        entity_id="entity_plant_001",
        category=ObservationCategory.PLANT_CONDITION,
        value=0.40,
        confidence=0.90,
    )

    assert (
        observation.state_key()
        == "entity_plant_001:plant_condition"
    )

#-7-
def test_current_observations_use_entity_state_key():
    state = HouseholdState(
        id="home_001"
    )

    observation = Observation(
        id="obs_001",
        source=ObservationSource.PHOTO,
        location="living_room",
        entity_id="entity_plant_001",
        category=ObservationCategory.PLANT_CONDITION,
        value=0.40,
        confidence=0.90,
    )

    state.add_observation(
        observation
    )

    assert (
        "entity_plant_001:plant_condition"
        in state.current_observations
    )

#-8-
def test_current_observations_keep_entities_separate():
    state = HouseholdState(
        id="home_001"
    )

    plant_one = Observation(
        id="obs_001",
        source=ObservationSource.PHOTO,
        location="living_room",
        entity_id="entity_plant_001",
        category=ObservationCategory.PLANT_CONDITION,
        value=0.30,
        confidence=0.90,
    )
    plant_two = Observation(
        id="obs_002",
        source=ObservationSource.PHOTO,
        location="living_room",
        entity_id="entity_plant_002",
        category=ObservationCategory.PLANT_CONDITION,
        value=0.80,
        confidence=0.90,
    )

    state.add_observation(plant_one)
    state.add_observation(plant_two)

    assert len(
        state.current_observations
    ) == 2

    assert (
        "entity_plant_001:plant_condition"
        in state.current_observations
    )
    assert (
        "entity_plant_002:plant_condition"
        in state.current_observations
    )
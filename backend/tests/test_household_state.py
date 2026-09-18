from app.models import HouseholdState, Observation


def test_household_state_starts_empty():
    state = HouseholdState(id="home_001")

    assert state.observation_history == []
    assert state.current_observations == {}


def test_add_observation_updates_state():
    state = HouseholdState(id="home_001")

    observation = Observation(
        id="obs_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.82,
        confidence=0.91,
    )

    state.add_observation(observation)

    assert len(state.observation_history) == 1
    assert len(state.current_observations) == 1

    assert (
        state.current_observations["kitchen:dish_load"].value
        == 0.82
    )


def test_new_observation_replaces_current_but_preserves_history():
    state = HouseholdState(id="home_001")

    first_observation = Observation(
        id="obs_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.82,
        confidence=0.91,
    )

    second_observation = Observation(
        id="obs_002",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.35,
        confidence=0.94,
    )

    state.add_observation(first_observation)
    state.add_observation(second_observation)

    assert len(state.observation_history) == 2
    assert len(state.current_observations) == 1

    current = state.current_observations["kitchen:dish_load"]

    assert current.id == "obs_002"
    assert current.value == 0.35
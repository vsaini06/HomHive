from app.models import HouseholdState, ObservationSource
from app.repositories.observation_storage import ObservationStorage


def reconstruct_household_state(household_id: str, storage: ObservationStorage) -> HouseholdState:
    if not household_id:
        raise ValueError("household_id must not be empty")

    state = HouseholdState(id=household_id)
    history = storage.list_observations(household_id)


    history.sort(key=lambda observation: (
        observation.timestamp,
        bool(observation.source == ObservationSource.USER_INPUT
             and observation.metadata.get("confirmed_observation_id")),
    ))
    for observation in history:
        state.add_observation(observation)
    return state

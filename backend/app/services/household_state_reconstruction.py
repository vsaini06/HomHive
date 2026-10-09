from app.models import HouseholdState
from app.repositories.observation_storage import ObservationStorage


def reconstruct_household_state(household_id: str, storage: ObservationStorage) -> HouseholdState:
    if not household_id:
        raise ValueError("household_id must not be empty")

    state = HouseholdState(id=household_id)
    for observation in storage.list_observations(household_id):
        state.add_observation(observation)
    return state

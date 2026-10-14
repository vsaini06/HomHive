from uuid import uuid4

from app.models import Observation, ObservationSource
from app.repositories.observation_storage import ObservationStorage


def confirm_observation(
    household_id: str,
    observation_id: str,
    confirmed_value: float,
    storage: ObservationStorage,
) -> Observation | None:
    original = storage.find_observation(household_id, observation_id)
    if original is None:
        return None

    confirmation = Observation(
        id=str(uuid4()),
        source=ObservationSource.USER_INPUT,
        location=original.location,
        entity_id=original.entity_id,
        category=original.category,
        value=confirmed_value,
        confidence=1.0,
        metadata={
            "confirmed_observation_id": original.id,
            "source_media_id": original.metadata.get("media_id"),
        },
    )
    return storage.add_observation(household_id, confirmation)

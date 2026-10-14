from app.models import ConditionType, Observation, ObservationSource
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.services.observation_review import confirm_observation


def test_confirm_observation_preserves_original_and_adds_user_evidence():
    storage = InMemoryObservationRepository()
    original = Observation(
        id="vision-1",
        source=ObservationSource.PHOTO,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=0.8,
        confidence=None,
        metadata={"media_id": "media-1"},
    )
    storage.add_observation("home", original)

    confirmed = confirm_observation("home", "vision-1", 0.7, storage)

    assert confirmed is not None
    assert confirmed.source == ObservationSource.USER_INPUT
    assert confirmed.value == 0.7
    assert confirmed.confidence == 1.0
    assert confirmed.metadata["confirmed_observation_id"] == "vision-1"
    assert len(storage.list_observations("home")) == 2


def test_confirm_unknown_observation_returns_none():
    storage = InMemoryObservationRepository()
    assert confirm_observation("home", "missing", 0.5, storage) is None

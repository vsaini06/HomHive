from datetime import datetime, timedelta, timezone

import pytest

from app.models import Observation
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.repositories.observation_storage import ObservationStorage


def observation(observation_id: str, timestamp: datetime, value: float = 0.8) -> Observation:
    return Observation(
        id=observation_id,
        source="photo",
        location="kitchen",
        category="dish_load",
        value=value,
        confidence=0.9,
        timestamp=timestamp,
        metadata={"labels": ["dishes"]},
    )


def test_repository_satisfies_observation_storage_contract():
    assert isinstance(InMemoryObservationRepository(), ObservationStorage)


def test_observations_are_scoped_to_household():
    repository = InMemoryObservationRepository()
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repository.add_observation("home_a", observation("obs_1", timestamp))
    repository.add_observation("home_b", observation("obs_1", timestamp, value=0.3))

    assert repository.find_observation("home_a", "obs_1").value == 0.8
    assert repository.find_observation("home_b", "obs_1").value == 0.3
    assert repository.find_observation("home_c", "obs_1") is None
    assert repository.list_observations("home_c") == []


def test_observation_history_is_chronological():
    repository = InMemoryObservationRepository()
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repository.add_observation("home", observation("later", timestamp + timedelta(hours=1)))
    repository.add_observation("home", observation("earlier", timestamp))

    assert [item.id for item in repository.list_observations("home")] == ["earlier", "later"]


def test_duplicate_observation_does_not_overwrite_evidence():
    repository = InMemoryObservationRepository()
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repository.add_observation("home", observation("obs_1", timestamp))

    with pytest.raises(ValueError, match="already exists"):
        repository.add_observation("home", observation("obs_1", timestamp, value=0.2))

    assert repository.find_observation("home", "obs_1").value == 0.8


def test_observations_are_isolated_from_caller_mutations():
    repository = InMemoryObservationRepository()
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    original = observation("obs_1", timestamp)
    repository.add_observation("home", original)
    original.metadata["labels"].append("changed")
    retrieved = repository.find_observation("home", "obs_1")
    retrieved.metadata["labels"].append("modified")
    repository.list_observations("home")[0].value = 0.1

    stored = repository.find_observation("home", "obs_1")
    assert stored.metadata == {"labels": ["dishes"]}
    assert stored.value == 0.8


def test_household_identifier_is_required_for_writes():
    repository = InMemoryObservationRepository()
    with pytest.raises(ValueError, match="household_id"):
        repository.add_observation("", observation("obs_1", datetime.now(timezone.utc)))

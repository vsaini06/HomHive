from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.observation_record import ObservationRecord
from app.models import Observation
from app.repositories.observation_storage import ObservationStorage
from app.repositories.sqlalchemy_observation_repository import SQLAlchemyObservationRepository


@pytest.fixture
def repository_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'observations.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield lambda: SQLAlchemyObservationRepository(factory)
    engine.dispose()


def observation(observation_id, timestamp=None, value=0.8):
    return Observation(
        id=observation_id,
        source="photo",
        location="kitchen",
        entity_id="sink_01",
        category="dish_load",
        value=value,
        confidence=0.9,
        timestamp=timestamp or datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata={"labels": ["dishes"]},
    )


def test_sql_repository_satisfies_observation_storage_contract(repository_factory):
    assert isinstance(repository_factory(), ObservationStorage)


def test_saved_observation_survives_independent_repository_instances(repository_factory):
    repository_factory().add_observation("home_a", observation("obs_1"))
    retrieved = repository_factory().find_observation("home_a", "obs_1")
    assert retrieved == observation("obs_1")


def test_identical_observation_ids_can_belong_to_different_households(repository_factory):
    repository_factory().add_observation("home_a", observation("obs_1"))
    repository_factory().add_observation("home_b", observation("obs_1", value=0.3))
    assert repository_factory().find_observation("home_a", "obs_1").value == 0.8
    assert repository_factory().find_observation("home_b", "obs_1").value == 0.3
    assert repository_factory().find_observation("home_c", "obs_1") is None


def test_history_is_chronological_with_stable_tie_break(repository_factory):
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repo = repository_factory()
    repo.add_observation("home", observation("b", earlier + timedelta(hours=1)))
    repo.add_observation("home", observation("c", earlier))
    repo.add_observation("home", observation("a", earlier))
    assert [item.id for item in repository_factory().list_observations("home")] == ["a", "c", "b"]
    assert repository_factory().list_observations("other") == []


def test_duplicate_observation_is_rejected_without_replacing_original(repository_factory):
    repo = repository_factory()
    repo.add_observation("home", observation("obs_1"))
    with pytest.raises(ValueError, match="already exists"):
        repo.add_observation("home", observation("obs_1", value=0.2))
    assert repository_factory().find_observation("home", "obs_1").value == 0.8


def test_metadata_changes_do_not_mutate_saved_evidence(repository_factory):
    original = observation("obs_1")
    repo = repository_factory()
    repo.add_observation("home", original)
    original.metadata["labels"].append("extra")
    retrieved = repo.find_observation("home", "obs_1")
    retrieved.metadata["labels"].append("changed")
    assert repository_factory().find_observation("home", "obs_1").metadata == {"labels": ["dishes"]}


def test_household_identifier_required_for_writes(repository_factory):
    with pytest.raises(ValueError, match="household_id"):
        repository_factory().add_observation("", observation("obs_1"))


def test_observation_table_registered():
    assert ObservationRecord.__table__ is Base.metadata.tables["observations"]

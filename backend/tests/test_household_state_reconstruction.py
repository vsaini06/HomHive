from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.observation_record import ObservationRecord
from app.models import Observation
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.repositories.sqlalchemy_observation_repository import SQLAlchemyObservationRepository
from app.services.household_state_reconstruction import reconstruct_household_state


def observation(observation_id: str, timestamp: datetime, value: float, entity_id: str | None = None) -> Observation:
    return Observation(
        id=observation_id,
        source="photo",
        location="kitchen",
        entity_id=entity_id,
        category="dish_load",
        value=value,
        confidence=0.9,
        timestamp=timestamp,
    )


def test_empty_household_reconstructs_empty_state():
    state = reconstruct_household_state("home", InMemoryObservationRepository())
    assert state.id == "home"
    assert state.observation_history == []
    assert state.current_observations == {}


def test_reconstructed_state_replays_history_in_chronological_order():
    storage = InMemoryObservationRepository()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    storage.add_observation("home", observation("later", start + timedelta(hours=2), 0.9))
    storage.add_observation("home", observation("earlier", start, 0.3))
    state = reconstruct_household_state("home", storage)
    assert [item.id for item in state.observation_history] == ["earlier", "later"]
    assert state.current_observations["kitchen:dish_load"].id == "later"


def test_reconstruction_distinguishes_entity_conditions():
    storage = InMemoryObservationRepository()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    storage.add_observation("home", observation("sink", start, 0.8, "sink_01"))
    storage.add_observation("home", observation("counter", start, 0.4, "counter_01"))
    state = reconstruct_household_state("home", storage)
    assert set(state.current_observations) == {"sink_01:dish_load", "counter_01:dish_load"}


def test_reconstruction_keeps_households_isolated():
    storage = InMemoryObservationRepository()
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    storage.add_observation("home_a", observation("same", timestamp, 0.2))
    storage.add_observation("home_b", observation("same", timestamp, 0.9))
    assert reconstruct_household_state("home_a", storage).current_observations["kitchen:dish_load"].value == 0.2
    assert reconstruct_household_state("home_b", storage).current_observations["kitchen:dish_load"].value == 0.9


def test_reconstruction_requires_household_id():
    with pytest.raises(ValueError, match="household_id"):
        reconstruct_household_state("", InMemoryObservationRepository())


def test_sql_history_reconstructs_state_across_sessions(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'history.sqlite'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    try:
        writer = SQLAlchemyObservationRepository(session_factory)
        writer.add_observation("home", observation("older", start, 0.2))
        writer.add_observation("home", observation("newer", start + timedelta(hours=1), 0.8))
        reader = SQLAlchemyObservationRepository(session_factory)
        state = reconstruct_household_state("home", reader)
        assert [item.id for item in state.observation_history] == ["older", "newer"]
        assert state.current_observations["kitchen:dish_load"].value == 0.8
    finally:
        engine.dispose()

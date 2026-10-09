"""Durability and contract tests for SQL-backed household entity storage."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.session import build_engine, build_session_factory
from app.models import EntityType, HouseholdEntity
from app.repositories.household_entity_storage import HouseholdEntityStorage
from app.repositories.sqlalchemy_household_entity_repository import SQLAlchemyHouseholdEntityRepository
from app.services.household_entity_service import HouseholdEntityService


@pytest.fixture
def storage(tmp_path):
    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    database = tmp_path / "entities.sqlite3"
    url = f"sqlite:///{database.as_posix()}"
    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    # Migration environment resolves DATABASE_URL at execution time.
    import os
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(cfg, "head")
    finally:
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url
    engine = build_engine(url)
    factory = build_session_factory(engine)
    yield SQLAlchemyHouseholdEntityRepository(factory), factory
    engine.dispose()


def make_entity(entity_id="plant_001", **changes):
    payload = dict(id=entity_id, entity_type=EntityType.PLANT,
                   name="Kitchen Plant", location="kitchen",
                   identity="Monstera deliciosa",
                   attributes={"care": {"watering_days": [3, 7]}})
    payload.update(changes)
    return HouseholdEntity(**payload)


def test_storage_satisfies_application_contract(storage):
    repository, _ = storage
    assert isinstance(repository, HouseholdEntityStorage)
    assert HouseholdEntityService(repository).list_entities() == []


def test_create_survives_independent_sessions(storage):
    repository, factory = storage
    created = repository.create_entity(make_entity())
    assert created.id == "plant_001"
    separate_repository = SQLAlchemyHouseholdEntityRepository(factory)
    retrieved = separate_repository.find_by_id("plant_001")
    assert retrieved is not None
    assert retrieved.attributes == {"care": {"watering_days": [3, 7]}}
    retrieved.attributes["care"]["watering_days"].append(10)
    assert separate_repository.find_by_id("plant_001").attributes == {"care": {"watering_days": [3, 7]}}


def test_filter_and_list(storage):
    repository, _ = storage
    repository.create_entity(make_entity("a"))
    repository.create_entity(make_entity("b", location="living_room"))
    repository.create_entity(make_entity("c", entity_type=EntityType.APPLIANCE))
    assert [e.id for e in repository.list_entities(location="kitchen")] == ["a", "c"]
    assert [e.id for e in repository.list_entities(entity_type=EntityType.PLANT)] == ["a", "b"]
    assert [e.id for e in repository.list_entities(location="kitchen", entity_type=EntityType.PLANT)] == ["a"]


def test_service_rename_commits_across_sessions(storage):
    repository, factory = storage
    repository.create_entity(make_entity())
    changed = HouseholdEntityService(repository).rename_entity("plant_001", "  New Name  ")
    assert changed.name == "New Name"
    independent = SQLAlchemyHouseholdEntityRepository(factory)
    assert independent.find_by_id("plant_001").name == "New Name"
    assert independent.rename_entity("missing", "unused") is None


def test_duplicate_id_rolls_back_transaction(storage):
    repository, _ = storage
    repository.create_entity(make_entity())
    with pytest.raises(IntegrityError):
        repository.create_entity(make_entity(name="Duplicate"))
    assert [e.name for e in repository.list_entities()] == ["Kitchen Plant"]


def test_missing_entity_returns_none(storage):
    repository, _ = storage
    assert repository.find_by_id("missing") is None
    assert repository.rename_entity("missing", "Other") is None

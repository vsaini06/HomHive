"""Storage selection and session ownership behavior."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.entity_storage import build_entity_storage
from app.repositories.household_entity_repository import HouseholdEntityRepository
from app.repositories.sqlalchemy_household_entity_repository import (
    SQLAlchemyHouseholdEntityRepository,
)


def test_memory_storage_is_default(monkeypatch):
    monkeypatch.delenv("HOMHIVE_ENTITY_STORAGE", raising=False)
    storage, engine = build_entity_storage()
    assert isinstance(storage, HouseholdEntityRepository)
    assert engine is None


def test_storage_can_be_selected_from_environment(monkeypatch):
    monkeypatch.setenv("HOMHIVE_ENTITY_STORAGE", "memory")
    storage, _ = build_entity_storage()
    assert isinstance(storage, HouseholdEntityRepository)


def test_sql_storage_uses_injected_sessions():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        sessions = sessionmaker(engine, class_=Session)
        storage, owned_engine = build_entity_storage(
            storage_backend="sql", session_factory=sessions
        )
        assert isinstance(storage, SQLAlchemyHouseholdEntityRepository)
        assert owned_engine is None
    finally:
        engine.dispose()


def test_invalid_storage_configuration_fails():
    with pytest.raises(ValueError, match="HOMHIVE_ENTITY_STORAGE"):
        build_entity_storage(storage_backend="unknown")


def test_memory_storage_rejects_database_sessions():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with pytest.raises(ValueError, match="session_factory"):
            build_entity_storage(
                storage_backend="memory", session_factory=sessionmaker(engine)
            )
    finally:
        engine.dispose()

"""Configure household entity storage for an API instance."""

import os

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import build_engine, build_session_factory
from app.repositories.household_entity_repository import HouseholdEntityRepository
from app.repositories.household_entity_storage import HouseholdEntityStorage
from app.repositories.sqlalchemy_household_entity_repository import (
    SQLAlchemyHouseholdEntityRepository,
)


def build_entity_storage(
    *,
    storage_backend: str | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> tuple[HouseholdEntityStorage, Engine | None]:
    """Choose entity storage and return any engine owned by the caller.

    The SQL implementation requires an existing migrated database. Schema
    changes are performed explicitly with Alembic, not by application startup.
    """
    backend = (storage_backend or os.getenv("HOMHIVE_ENTITY_STORAGE", "memory")).strip().lower()
    if backend == "memory":
        if session_factory is not None:
            raise ValueError("session_factory requires SQL entity storage")
        return HouseholdEntityRepository(), None
    if backend != "sql":
        raise ValueError("HOMHIVE_ENTITY_STORAGE must be 'memory' or 'sql'")
    if session_factory is not None:
        return SQLAlchemyHouseholdEntityRepository(session_factory), None
    engine = build_engine()
    return SQLAlchemyHouseholdEntityRepository(build_session_factory(engine)), engine

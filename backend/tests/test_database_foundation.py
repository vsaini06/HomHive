"""Checkpoint 11.1 tests: no PostgreSQL instance required."""

import pytest
from sqlalchemy import text

from app.db.base import Base
from app.db.config import get_database_url
from app.db.session import build_engine, build_session_factory, session_scope

def test_database_url_missing_is_explicit(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        get_database_url()


def test_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    assert get_database_url() == "sqlite+pysqlite:///:memory:"


def test_engine_and_separate_sessions_work_without_tables(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'foundation.sqlite3'}"
    engine = build_engine(url)
    factory = build_session_factory(engine)
    try:
        with factory() as first:
            assert first.execute(text("SELECT 1")).scalar_one() == 1
        with factory() as second:
            assert second.execute(text("SELECT 2")).scalar_one() == 2
    finally:
        engine.dispose()


def test_session_scope_rolls_back_exception(tmp_path):
    engine = build_engine(f"sqlite+pysqlite:///{tmp_path / 'scope.sqlite3'}")
    factory = build_session_factory(engine)
    try:
        with pytest.raises(RuntimeError, match="failure"):
            with session_scope(factory) as session:
                session.execute(text("SELECT 1"))
                raise RuntimeError("failure")
    finally:
        engine.dispose()


def test_household_entity_table_registered():
    assert "household_entities" in Base.metadata.tables

    table = Base.metadata.tables["household_entities"]

    assert "id" in table.columns
    assert "name" in table.columns

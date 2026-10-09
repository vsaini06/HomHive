"""GraphQL storage wiring and persistence between API instances."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.app import create_app
from app.models import EntityType, HouseholdEntity
from app.repositories.sqlalchemy_household_entity_repository import (
    SQLAlchemyHouseholdEntityRepository,
)


def test_graphql_persists_renames_between_app_instances(tmp_path: Path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'entities.sqlite'}"
    engine = create_engine(database_url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    # Alembic obtains its URL from the environment for both migration modes.
    import os
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url

    sessions = sessionmaker(engine, expire_on_commit=False)
    try:
        storage = SQLAlchemyHouseholdEntityRepository(sessions)
        storage.create_entity(HouseholdEntity(
            id="plant_42", entity_type=EntityType.PLANT,
            name="Window Plant", location="living_room"
        ))
        with TestClient(create_app(
            entity_storage_backend="sql", entity_session_factory=sessions
        )) as client:
            response = client.post("/graphql", json={
                "query": 'mutation { renameEntity(id: "plant_42", name: "Sunny Plant") { id name } }'
            })
            assert response.json() == {"data": {"renameEntity": {
                "id": "plant_42", "name": "Sunny Plant"
            }}}
        with TestClient(create_app(
            entity_storage_backend="sql", entity_session_factory=sessions
        )) as client:
            response = client.post("/graphql", json={
                "query": 'query { entity(id: "plant_42") { id name } }'
            })
            assert response.json() == {"data": {"entity": {
                "id": "plant_42", "name": "Sunny Plant"
            }}}
    finally:
        engine.dispose()

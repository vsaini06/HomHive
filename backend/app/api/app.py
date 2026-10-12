"""HomHive API application factory."""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker
from strawberry.fastapi import GraphQLRouter

from app.config import load_local_environment
from app.services import HouseholdEntityService
from app.db.session import build_engine, build_session_factory
from app.media.api import build_media_router
from app.media.service import MediaService
from app.media.storage import LocalMediaStorage
from app.repositories.sqlalchemy_observation_repository import SQLAlchemyObservationRepository
from app.vision.api import build_vision_router
from app.vision.provider import NebiusVisionProvider
from app.vision.service import VisionObservationService

from .entity_storage import build_entity_storage
from .graphql.schema import create_schema


def create_app(
    *,
    entity_storage_backend: str | None = None,
    entity_session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    """Build an API instance with an isolated storage configuration."""
    load_local_environment()
    repository, owned_engine = build_entity_storage(
        storage_backend=entity_storage_backend,
        session_factory=entity_session_factory,
    )
    household_entity_service = HouseholdEntityService(repository=repository)
    media_engine = None
    media_root = os.environ.get('HOMHIVE_MEDIA_ROOT')
    household_tokens_json = os.environ.get('HOMHIVE_HOUSEHOLD_TOKENS')
    if media_root or household_tokens_json:
        if not (media_root and household_tokens_json):
            raise ValueError('Media storage and household tokens must both be configured')
        tokens = json.loads(household_tokens_json)
        if not isinstance(tokens, dict) or not tokens or not all(
            isinstance(key, str) and key and isinstance(value, str) and value
            for key, value in tokens.items()
        ):
            raise ValueError('Invalid household token configuration')
        media_engine = build_engine()
        media_service = MediaService(build_session_factory(media_engine), LocalMediaStorage(Path(media_root)))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if owned_engine is not None:
                owned_engine.dispose()
            if media_engine is not None:
                media_engine.dispose()

    app = FastAPI(title="HomHive API", version="0.1.0", lifespan=lifespan)

    async def graphql_context():
        """Expose application services to GraphQL resolvers."""
        return {"household_entity_service": household_entity_service}

    app.include_router(
        GraphQLRouter(create_schema(), context_getter=graphql_context),
        prefix="/graphql",
    )

    if media_engine is not None:
        app.include_router(build_media_router(media_service, tokens))
        if os.environ.get("NEBIUS_API_KEY"):
            vision_service = VisionObservationService(
                media_service, NebiusVisionProvider(),
                SQLAlchemyObservationRepository(build_session_factory(media_engine)),
            )
            app.include_router(build_vision_router(vision_service, tokens))

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

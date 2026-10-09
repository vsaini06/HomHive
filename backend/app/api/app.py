"""HomHive API application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker
from strawberry.fastapi import GraphQLRouter

from app.services import HouseholdEntityService

from .entity_storage import build_entity_storage
from .graphql.schema import create_schema


def create_app(
    *,
    entity_storage_backend: str | None = None,
    entity_session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    """Build an API instance with an isolated storage configuration."""
    repository, owned_engine = build_entity_storage(
        storage_backend=entity_storage_backend,
        session_factory=entity_session_factory,
    )
    household_entity_service = HouseholdEntityService(repository=repository)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if owned_engine is not None:
                owned_engine.dispose()

    app = FastAPI(title="HomHive API", version="0.1.0", lifespan=lifespan)

    async def graphql_context():
        """Expose application services to GraphQL resolvers."""
        return {"household_entity_service": household_entity_service}

    app.include_router(
        GraphQLRouter(create_schema(), context_getter=graphql_context),
        prefix="/graphql",
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

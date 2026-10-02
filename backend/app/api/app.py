from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.repositories import EntityRepository
from app.services import EntityService

from .graphql.schema import create_schema


def create_app() -> FastAPI:
    app = FastAPI(
        title="HomHive API",
        version="0.1.0",
    )

    entity_repository = EntityRepository()

    entity_service = EntityService(
        repository=entity_repository
    )

    async def get_context():
        return {
            "entity_service": entity_service,
        }

    graphql_app = GraphQLRouter(
        create_schema(),
        context_getter=get_context,
    )

    app.include_router(
        graphql_app,
        prefix="/graphql",
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
        }

    return app


app = create_app()
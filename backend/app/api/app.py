from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.repositories import (
    HouseholdEntityRepository,
)
from app.services import (
    HouseholdEntityService,
)

from .graphql.schema import create_schema


def create_app() -> FastAPI:
    """Build the HomHive API and its application-scoped dependencies."""

    app = FastAPI(
        title="HomHive API",
        version="0.1.0",
    )

    entity_repository = (
        HouseholdEntityRepository()
    )

    household_entity_service = (
        HouseholdEntityService(
            repository=entity_repository
        )
    )

    async def graphql_context():
        """Provide request handlers with the services owned by this app instance."""

        return {
            "household_entity_service": (
                household_entity_service
            ),

            # Keep the old key temporarily in case another caller still uses it.
            "entity_service": (
                household_entity_service
            ),
        }

    graphql_router = GraphQLRouter(
        create_schema(),
        context_getter=graphql_context,
    )

    app.include_router(
        graphql_router,
        prefix="/graphql",
    )

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
        }

    return app


app = create_app()
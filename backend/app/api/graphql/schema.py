import strawberry
from strawberry.types import Info

from app.models import EntityType
from app.services import EntityService

from .mappers import household_entity_to_graphql
from .types import (
    EntityTypeEnum,
    HouseholdEntityType,
)

@strawberry.type
class Query:

    @strawberry.field
    def entity(
        self,
        info: Info,
        id: str,
    ) -> HouseholdEntityType | None:
        entity_service: EntityService = (
            info.context["entity_service"]
        )

        domain_entity = (
            entity_service.get_entity(id)
        )

        if domain_entity is None:
            return None

        return household_entity_to_graphql(
            domain_entity
        )

    @strawberry.field
    def entities(
        self,
        info: Info,
        location: str | None = None,
        entity_type: EntityTypeEnum | None = None,
    ) -> list[HouseholdEntityType]:
        entity_service: EntityService = (
            info.context["entity_service"]
        )

        domain_entity_type = None

        if entity_type is not None:
            domain_entity_type = EntityType(
                entity_type.value
            )

        domain_entities = (
            entity_service.list_entities(
                location=location,
                entity_type=domain_entity_type,
            )
        )

        return [
            household_entity_to_graphql(entity)
            for entity in domain_entities
        ]

@strawberry.type
class Mutation:

    @strawberry.mutation
    def rename_entity(
        self,
        info: Info,
        id: str,
        name: str,
    ) -> HouseholdEntityType | None:
        entity_service: EntityService = (
            info.context["entity_service"]
        )

        domain_entity = (
            entity_service.rename_entity(
                entity_id=id,
                name=name,
            )
        )

        if domain_entity is None:
            return None

        return household_entity_to_graphql(
            domain_entity
        )

def create_schema() -> strawberry.Schema:
    return strawberry.Schema(
        query=Query,
        mutation=Mutation,
    )
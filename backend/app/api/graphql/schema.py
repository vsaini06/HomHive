import strawberry

from app.models import EntityType
from app.repositories import EntityRepository
from app.services import EntityService
from .mappers import household_entity_to_graphql
from .types import (
    EntityTypeEnum,
    HouseholdEntityType,
)

entity_repository = EntityRepository()
entity_service = EntityService(
    repository=entity_repository
)

@strawberry.type
class Query:

    @strawberry.field
    def entity(
        self,
        id: str,
    ) -> HouseholdEntityType | None:
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
        location: str | None = None,
        entity_type: EntityTypeEnum | None = None,
    ) -> list[HouseholdEntityType]:
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


schema = strawberry.Schema(
    query=Query
)
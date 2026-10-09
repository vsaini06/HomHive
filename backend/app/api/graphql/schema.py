import strawberry
from strawberry.types import Info

from app.models import EntityType
from app.services import HouseholdEntityService

from .household_entity_mapping import (
    to_household_entity_view,
)
from .household_entity_types import (
    HouseholdEntityKind,
    HouseholdEntityView,
)


def _household_entity_service(
    info: Info,
) -> HouseholdEntityService:
    """Return the entity service attached to this GraphQL request."""

    return info.context[
        "household_entity_service"
    ]


@strawberry.type
class Query:

    @strawberry.field
    def entity(
        self,
        info: Info,
        id: str,
    ) -> HouseholdEntityView | None:
        service = _household_entity_service(
            info
        )

        entity = service.find_entity(
            id
        )

        if entity is None:
            return None

        return to_household_entity_view(
            entity
        )

    @strawberry.field
    def entities(
        self,
        info: Info,
        location: str | None = None,
        entity_type: HouseholdEntityKind | None = None,
    ) -> list[HouseholdEntityView]:
        service = _household_entity_service(
            info
        )

        entity_type_filter = None

        if entity_type is not None:
            entity_type_filter = EntityType(
                entity_type.value
            )

        entities = service.list_entities(
            location=location,
            entity_type=entity_type_filter,
        )

        return [
            to_household_entity_view(entity)
            for entity in entities
        ]


@strawberry.type
class Mutation:

    @strawberry.mutation
    def rename_entity(
        self,
        info: Info,
        id: str,
        name: str,
    ) -> HouseholdEntityView | None:
        service = _household_entity_service(
            info
        )

        entity = service.rename_entity(
            entity_id=id,
            new_name=name,
        )

        if entity is None:
            return None

        return to_household_entity_view(
            entity
        )


def create_schema() -> strawberry.Schema:
    """Build the GraphQL schema exposed by the HomHive API."""

    return strawberry.Schema(
        query=Query,
        mutation=Mutation,
    )
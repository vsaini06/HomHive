from app.models import (
    EntityType,
    HouseholdEntity,
)
from app.repositories import EntityRepository


class EntityService:

    def __init__(
        self,
        repository: EntityRepository,
    ) -> None:
        self._repository = repository

    def get_entity(
        self,
        entity_id: str,
    ) -> HouseholdEntity | None:
        return self._repository.get_by_id(
            entity_id
        )

    def list_entities(
        self,
        location: str | None = None,
        entity_type: EntityType | None = None,
    ) -> list[HouseholdEntity]:
        return self._repository.list_entities(
            location=location,
            entity_type=entity_type,
        )
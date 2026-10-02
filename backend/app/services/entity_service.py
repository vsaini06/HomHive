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

    def rename_entity(
        self,
        entity_id: str,
        name: str,
    ) -> HouseholdEntity | None:
        cleaned_name = name.strip()

        if not cleaned_name:
            raise ValueError(
                "Entity name cannot be empty."
            )

        return self._repository.update_name(
            entity_id=entity_id,
            name=cleaned_name,
        )
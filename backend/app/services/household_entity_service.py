from app.models import (
    EntityType,
    HouseholdEntity,
)

from app.repositories import (
    HouseholdEntityRepository,
)


class HouseholdEntityService:
    """Handles application-level operations for known household entities."""

    def __init__(
        self,
        repository: HouseholdEntityRepository,
    ) -> None:
        self._repository = repository

    def find_entity(
        self,
        entity_id: str,
    ) -> HouseholdEntity | None:
        """Find one known household entity."""

        return self._repository.find_by_id(
            entity_id
        )

    def list_entities(
        self,
        location: str | None = None,
        entity_type: EntityType | None = None,
    ) -> list[HouseholdEntity]:
        """List known entities, optionally narrowed by location or type."""

        return self._repository.list_entities(
            location=location,
            entity_type=entity_type,
        )

    def rename_entity(
        self,
        entity_id: str,
        new_name: str | None = None,
        *,
        name: str | None = None,
    ) -> HouseholdEntity | None:
        """Rename an entity after cleaning and validating the supplied name."""

        # new_name is the preferred argument. name remains temporarily for
        # callers using the original service interface.
        requested_name = (
            new_name
            if new_name is not None
            else name
        )

        if requested_name is None:
            raise ValueError(
                "Entity name cannot be empty."
            )

        cleaned_name = (
            requested_name.strip()
        )

        if not cleaned_name:
            raise ValueError(
                "Entity name cannot be empty."
            )

        return self._repository.rename_entity(
            entity_id=entity_id,
            new_name=cleaned_name,
        )

    def get_entity(
        self,
        entity_id: str,
    ) -> HouseholdEntity | None:
        """Compatibility wrapper for find_entity()."""

        return self.find_entity(
            entity_id
        )
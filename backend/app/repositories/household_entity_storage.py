"""Storage contract for household entities. No database dependencies."""

from typing import Protocol, runtime_checkable

from app.models import EntityType, HouseholdEntity


@runtime_checkable
class HouseholdEntityStorage(Protocol):
    """Operations the entity application service requires from any store."""

    def find_by_id(self, entity_id: str) -> HouseholdEntity | None: ...

    def list_entities(
        self,
        location: str | None = None,
        entity_type: EntityType | None = None,
    ) -> list[HouseholdEntity]: ...

    def rename_entity(
        self, entity_id: str, new_name: str
    ) -> HouseholdEntity | None: ...

from app.models import (
    EntityType,
    HouseholdEntity,
)


class HouseholdEntityRepository:
    """Stores and retrieves the household entities HomHive currently knows about."""

    def __init__(self) -> None:
        # This is temporary in-memory data until the persistence layer replaces it.
        self._household_entities = [
            HouseholdEntity(
                id="entity_plant_001",
                entity_type=EntityType.PLANT,
                name="Living Room Plant",
                location="living_room",
                identity="Monstera deliciosa",
            ),
            HouseholdEntity(
                id="entity_washer_001",
                entity_type=EntityType.APPLIANCE,
                name="Laundry Room Washer",
                location="laundry_room",
                identity="LG WM4000HWA",
            ),
        ]

    def find_by_id(
        self,
        entity_id: str,
    ) -> HouseholdEntity | None:
        """Find one household entity by its stable ID."""

        return next(
            (
                entity
                for entity in self._household_entities
                if entity.id == entity_id
            ),
            None,
        )

    def list_entities(
        self,
        location: str | None = None,
        entity_type: EntityType | None = None,
    ) -> list[HouseholdEntity]:
        """Return household entities that match the supplied filters."""

        matching_entities = (
            self._household_entities
        )

        if location is not None:
            matching_entities = [
                entity
                for entity in matching_entities
                if entity.location == location
            ]

        if entity_type is not None:
            matching_entities = [
                entity
                for entity in matching_entities
                if entity.entity_type == entity_type
            ]

        return list(
            matching_entities
        )

    def rename_entity(
        self,
        entity_id: str,
        new_name: str,
    ) -> HouseholdEntity | None:
        """Change the user-facing name of a known household entity."""

        entity = self.find_by_id(
            entity_id
        )

        if entity is None:
            return None

        entity.name = new_name

        return entity

    # Existing callers still use the original repository method names.
    # Keep these until the API and tests have moved to the new vocabulary.

    def get_by_id(
        self,
        entity_id: str,
    ) -> HouseholdEntity | None:
        return self.find_by_id(
            entity_id
        )

    def update_name(
        self,
        entity_id: str,
        name: str,
    ) -> HouseholdEntity | None:
        return self.rename_entity(
            entity_id=entity_id,
            new_name=name,
        )
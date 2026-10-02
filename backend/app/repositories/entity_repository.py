from app.models import (
    EntityType,
    HouseholdEntity,
)


class EntityRepository:

    def __init__(self) -> None:
        self._entities = [
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

    def get_by_id(
        self,
        entity_id: str,
    ) -> HouseholdEntity | None:
        return next(
            (
                entity
                for entity in self._entities
                if entity.id == entity_id
            ),
            None,
        )

    def list_entities(
        self,
        location: str | None = None,
        entity_type: EntityType | None = None,
    ) -> list[HouseholdEntity]:
        entities = self._entities

        if location is not None:
            entities = [
                entity
                for entity in entities
                if entity.location == location
            ]

        if entity_type is not None:
            entities = [
                entity
                for entity in entities
                if entity.entity_type == entity_type
            ]

        return list(entities)

    def update_name(
    self,
    entity_id: str,
    name: str,
    ) -> HouseholdEntity | None:
        entity = self.get_by_id(
            entity_id
        )

        if entity is None:
            return None

        entity.name = name

        return entity
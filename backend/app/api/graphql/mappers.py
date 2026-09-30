from app.models import HouseholdEntity

from .types import (
    EntityTypeEnum,
    HouseholdEntityType,
)

def household_entity_to_graphql(
    entity: HouseholdEntity,
) -> HouseholdEntityType:
    return HouseholdEntityType(
        id=entity.id,
        name=entity.name,
        location=entity.location,
        identity=entity.identity,
        entity_type=EntityTypeEnum(
            entity.entity_type.value
        ),
    )
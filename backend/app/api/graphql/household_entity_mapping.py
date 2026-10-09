from app.models import HouseholdEntity

from .household_entity_types import (
    HouseholdEntityKind,
    HouseholdEntityView,
)


def to_household_entity_view(
    entity: HouseholdEntity,
) -> HouseholdEntityView:
    """Translate the domain entity into the shape exposed by GraphQL."""

    return HouseholdEntityView(
        id=entity.id,
        name=entity.name,
        location=entity.location,
        identity=entity.identity,
        entity_type=HouseholdEntityKind(
            entity.entity_type.value
        ),
    )
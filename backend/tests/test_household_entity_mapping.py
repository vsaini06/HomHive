from app.api.graphql.household_entity_mapping import (
    to_household_entity_view,
)
from app.api.graphql.household_entity_types import HouseholdEntityKind
from app.models import (
    EntityType,
    HouseholdEntity,
)

#-tests-

#-1-
def test_to_household_entity_view():
    entity = HouseholdEntity(
        id="entity_plant_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )

    graphql_entity = to_household_entity_view(
        entity
    )

    assert graphql_entity.id == "entity_plant_001"
    assert graphql_entity.name == "Living Room Plant"
    assert graphql_entity.entity_type == HouseholdEntityKind.PLANT
    assert graphql_entity.location == "living_room"
    assert (
        graphql_entity.identity
        == "Monstera deliciosa"
    )
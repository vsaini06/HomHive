from app.api.graphql.mappers import (
    household_entity_to_graphql,
)
from app.api.graphql.types import EntityTypeEnum
from app.models import (
    EntityType,
    HouseholdEntity,
)

#-tests-

#-1-
def test_household_entity_to_graphql():
    entity = HouseholdEntity(
        id="entity_plant_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
    )

    graphql_entity = household_entity_to_graphql(
        entity
    )

    assert graphql_entity.id == "entity_plant_001"
    assert graphql_entity.name == "Living Room Plant"
    assert graphql_entity.entity_type == EntityTypeEnum.PLANT
    assert graphql_entity.location == "living_room"
    assert (
        graphql_entity.identity
        == "Monstera deliciosa"
    )
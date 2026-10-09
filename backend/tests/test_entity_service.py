import pytest
from app.models import EntityType
from app.repositories import HouseholdEntityRepository
from app.services import HouseholdEntityService

#-tests-

#-1-
def test_entity_service_gets_entity():
    repository = HouseholdEntityRepository()
    service = HouseholdEntityService(
        repository=repository
    )
    entity = service.find_entity(
        "entity_plant_001"
    )

    assert entity is not None
    assert entity.id == "entity_plant_001"

#-2-
def test_entity_service_returns_none_for_unknown_entity():
    repository = HouseholdEntityRepository()
    service = HouseholdEntityService(
        repository=repository
    )
    entity = service.find_entity(
        "does_not_exist"
    )

    assert entity is None

#-3-
def test_entity_service_lists_entities():
    repository = HouseholdEntityRepository()
    service = HouseholdEntityService(
        repository=repository
    )
    entities = service.list_entities()

    assert len(entities) == 2

#-4-
def test_entity_service_filters_entities():
    repository = HouseholdEntityRepository()
    service = HouseholdEntityService(
        repository=repository
    )
    entities = service.list_entities(
        location="living_room",
        entity_type=EntityType.PLANT,
    )

    assert len(entities) == 1
    assert (
        entities[0].id
        == "entity_plant_001"
    )

#-5-
def test_entity_service_renames_entity():
    repository = HouseholdEntityRepository()
    service = HouseholdEntityService(
        repository=repository
    )
    entity = service.rename_entity(
        entity_id="entity_plant_001",
        new_name="  My Monstera  ",
    )

    assert entity is not None
    assert entity.name == "My Monstera"

#-6-
def test_entity_service_rejects_empty_name():
    repository = HouseholdEntityRepository()
    service = HouseholdEntityService(
        repository=repository
    )
    with pytest.raises(
        ValueError,
        match="Entity name cannot be empty.",
    ):
        service.rename_entity(
            entity_id="entity_plant_001",
            new_name="   ",
        )
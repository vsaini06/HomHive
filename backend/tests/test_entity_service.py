from app.models import EntityType
from app.repositories import EntityRepository
from app.services import EntityService

#-tests-

#-1-
def test_entity_service_gets_entity():
    repository = EntityRepository()
    service = EntityService(
        repository=repository
    )
    entity = service.get_entity(
        "entity_plant_001"
    )

    assert entity is not None
    assert entity.id == "entity_plant_001"

#-2-
def test_entity_service_returns_none_for_unknown_entity():
    repository = EntityRepository()
    service = EntityService(
        repository=repository
    )
    entity = service.get_entity(
        "does_not_exist"
    )

    assert entity is None

#-3-
def test_entity_service_lists_entities():
    repository = EntityRepository()
    service = EntityService(
        repository=repository
    )
    entities = service.list_entities()

    assert len(entities) == 2

#-4-
def test_entity_service_filters_entities():
    repository = EntityRepository()
    service = EntityService(
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
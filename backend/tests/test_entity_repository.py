from app.models import EntityType
from app.repositories import EntityRepository

#-tests-

#-1-
def test_entity_repository_gets_entity_by_id():
    repository = EntityRepository()

    entity = repository.get_by_id(
        "entity_plant_001"
    )

    assert entity is not None
    assert entity.id == "entity_plant_001"
    assert entity.name == "Living Room Plant"

#-2-
def test_entity_repository_returns_none_for_unknown_id():
    repository = EntityRepository()

    entity = repository.get_by_id(
        "does_not_exist"
    )

    assert entity is None

#-3-
def test_entity_repository_filters_by_location():
    repository = EntityRepository()

    entities = repository.list_entities(
        location="laundry_room"
    )

    assert len(entities) == 1
    assert (
        entities[0].id
        == "entity_washer_001"
    )

#-4-
def test_entity_repository_filters_by_entity_type():
    repository = EntityRepository()

    entities = repository.list_entities(
        entity_type=EntityType.PLANT
    )

    assert len(entities) == 1
    assert (
        entities[0].id
        == "entity_plant_001"
    )
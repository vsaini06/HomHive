"""Day 11 checkpoint 11.2: storage interface and pure mapping tests."""

from datetime import datetime, timezone

from app.db.household_entity_mapping import to_entity_record, to_household_entity
from app.db.household_entity_record import HouseholdEntityRecord
from app.models import EntityType, HouseholdEntity
from app.repositories import HouseholdEntityRepository, HouseholdEntityStorage
from app.services.household_entity_service import HouseholdEntityService


def test_existing_memory_repository_conforms_to_contract():
    assert isinstance(HouseholdEntityRepository(), HouseholdEntityStorage)


def test_service_accepts_storage_contract_and_renames():
    repository = HouseholdEntityRepository()
    service = HouseholdEntityService(repository)
    entity = service.rename_entity("entity_plant_001", "  New Label  ")
    assert entity is not None and entity.name == "New Label"
    assert repository.find_by_id("entity_plant_001").name == "New Label"


def test_orm_mapping_round_trip_preserves_all_domain_fields():
    timestamp = datetime(2026, 10, 9, 8, 30, tzinfo=timezone.utc)
    original = HouseholdEntity(
        id="plant-42", entity_type=EntityType.PLANT, name="Fern",
        location="balcony", identity="Nephrolepis exaltata",
        identification_confidence=0.89, attributes={"light": "indirect", "tags": ["a"]},
        created_at=timestamp, updated_at=timestamp,
    )
    record = to_entity_record(original)
    assert isinstance(record, HouseholdEntityRecord)
    assert record.entity_type == original.entity_type.value
    assert to_household_entity(record) == original
    record.attributes["tags"].append("changed")
    assert original.attributes["tags"] == ["a"]


def test_mapping_allows_optional_identity_fields():
    entity = HouseholdEntity(id="appliance-1", entity_type=EntityType.APPLIANCE,
                             name="Dryer", location="laundry_room")
    assert to_household_entity(to_entity_record(entity)) == entity


def test_orm_record_does_not_extend_domain_model():
    assert not issubclass(HouseholdEntityRecord, HouseholdEntity)

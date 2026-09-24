import pytest
from pydantic import ValidationError

from app.models import (
    EntityType,
    HouseholdEntity,
)

#-tests-

#-1-
def test_household_entity_creation():
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
    )

    assert entity.id == "entity_001"
    assert entity.entity_type == EntityType.PLANT
    assert entity.name == "Living Room Plant"
    assert entity.location == "living_room"
    assert entity.identity is None
    assert entity.identification_confidence is None
    assert entity.attributes == {}

#-2-
def test_household_entity_with_identity():
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
        identity="Monstera deliciosa",
        identification_confidence=0.94,
    )

    assert entity.identity == "Monstera deliciosa"
    assert entity.identification_confidence == 0.94

#-3-
def test_household_entity_supports_attributes():
    entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.APPLIANCE,
        name="Main Washing Machine",
        location="laundry_room",
        identity="LG WM4000HWA",
        identification_confidence=0.99,
        attributes={
            "brand": "LG",
            "model": "WM4000HWA",
        },
    )

    assert entity.attributes["brand"] == "LG"
    assert entity.attributes["model"] == "WM4000HWA"

#-4-
def test_identification_confidence_cannot_exceed_one():
    with pytest.raises(ValidationError):
        HouseholdEntity(
            id="entity_001",
            entity_type=EntityType.PLANT,
            name="Living Room Plant",
            location="living_room",
            identity="Monstera deliciosa",
            identification_confidence=1.1,
        )

#-5-
def test_identification_confidence_cannot_be_negative():
    with pytest.raises(ValidationError):
        HouseholdEntity(
            id="entity_001",
            entity_type=EntityType.PLANT,
            name="Living Room Plant",
            location="living_room",
            identity="Monstera deliciosa",
            identification_confidence=-0.1,
        )

#-6-
def test_household_entity_name_cannot_be_empty():
    with pytest.raises(ValidationError):
        HouseholdEntity(
            id="entity_001",
            entity_type=EntityType.PLANT,
            name="",
            location="living_room",
        )

#-7-
def test_household_entity_location_cannot_be_empty():
    with pytest.raises(ValidationError):
        HouseholdEntity(
            id="entity_001",
            entity_type=EntityType.PLANT,
            name="Living Room Plant",
            location="",
        )

#-8-
def test_household_entities_have_independent_attributes():
    first_entity = HouseholdEntity(
        id="entity_001",
        entity_type=EntityType.PLANT,
        name="Living Room Plant",
        location="living_room",
    )
    second_entity = HouseholdEntity(
        id="entity_002",
        entity_type=EntityType.PLANT,
        name="Bedroom Plant",
        location="bedroom",
    )

    first_entity.attributes["species"] = (
        "Monstera deliciosa"
    )

    assert (
        first_entity.attributes["species"]
        == "Monstera deliciosa"
    )
    assert second_entity.attributes == {}
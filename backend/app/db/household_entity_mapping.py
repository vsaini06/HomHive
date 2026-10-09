"""Explicit conversion between persistence and domain representations."""

from copy import deepcopy

from app.models import EntityType, HouseholdEntity

from .household_entity_record import HouseholdEntityRecord


def to_entity_record(entity: HouseholdEntity) -> HouseholdEntityRecord:
    """Build a new ORM record from a validated domain entity."""
    return HouseholdEntityRecord(
        id=entity.id,
        entity_type=entity.entity_type.value,
        name=entity.name,
        location=entity.location,
        identity=entity.identity,
        identification_confidence=entity.identification_confidence,
        attributes=deepcopy(entity.attributes),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def to_household_entity(record: HouseholdEntityRecord) -> HouseholdEntity:
    """Validate data read from the ORM against the domain contract."""
    return HouseholdEntity(
        id=record.id,
        entity_type=EntityType(record.entity_type),
        name=record.name,
        location=record.location,
        identity=record.identity,
        identification_confidence=record.identification_confidence,
        attributes=deepcopy(record.attributes),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

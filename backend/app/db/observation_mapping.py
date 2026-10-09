from copy import deepcopy
from datetime import timezone

from app.models import ConditionType, Observation, ObservationSource

from .observation_record import ObservationRecord


def to_observation_record(household_id: str, observation: Observation) -> ObservationRecord:
    return ObservationRecord(
        household_id=household_id,
        id=observation.id,
        source=observation.source.value,
        location=observation.location,
        entity_id=observation.entity_id,
        category=observation.category.value,
        value=observation.value,
        confidence=observation.confidence,
        timestamp=observation.timestamp,
        observation_metadata=deepcopy(observation.metadata),
    )


def to_observation(record: ObservationRecord) -> Observation:
    timestamp = record.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return Observation(
        id=record.id,
        source=ObservationSource(record.source),
        location=record.location,
        entity_id=record.entity_id,
        category=ConditionType(record.category),
        value=record.value,
        confidence=record.confidence,
        timestamp=timestamp,
        metadata=deepcopy(record.observation_metadata),
    )

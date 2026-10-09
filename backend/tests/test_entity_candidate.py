import pytest
from pydantic import ValidationError

from app.models import (
    EntityCandidate,
    EntityType,
)

#-Rules-

#-1-
def test_identification_candidate_creation():
    candidate = EntityCandidate(
        entity_type=EntityType.PLANT,
        identity="Monstera deliciosa",
        confidence=0.88,
        attributes={
            "leaf_shape": "split",
        },
        evidence=[
            "large split leaves",
        ],
    )

    assert candidate.entity_type == EntityType.PLANT
    assert candidate.identity == "Monstera deliciosa"
    assert candidate.confidence == 0.88
    assert candidate.attributes["leaf_shape"] == "split"
    assert candidate.evidence == [
        "large split leaves"
    ]

#-2-
def test_identification_candidate_allows_unknown_identity():
    candidate = EntityCandidate(
        entity_type=EntityType.APPLIANCE,
        identity=None,
        confidence=0.75,
    )

    assert candidate.identity is None
    assert candidate.confidence == 0.75

#-3-
def test_identification_candidate_rejects_confidence_above_one():
    with pytest.raises(ValidationError):
        EntityCandidate(
            entity_type=EntityType.PLANT,
            identity="Monstera deliciosa",
            confidence=1.1,
        )

#-4-
def test_identification_candidate_rejects_negative_confidence():
    with pytest.raises(ValidationError):
        EntityCandidate(
            entity_type=EntityType.PLANT,
            identity="Monstera deliciosa",
            confidence=-0.1,
        )
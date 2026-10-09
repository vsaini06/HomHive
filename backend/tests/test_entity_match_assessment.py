import pytest
from pydantic import ValidationError

from app.models import EntityMatchAssessment

#-tests-

#-1-
def test_entity_match_assessment_creation():
    evidence = EntityMatchAssessment(
        entity_id="entity_plant_001",
        score=0.92,
        reasons=[
            "same location",
            "matching visible attributes",
        ],
    )

    assert evidence.entity_id == "entity_plant_001"
    assert evidence.score == 0.92
    assert len(evidence.reasons) == 2

#-2-
def test_entity_match_assessment_allows_zero_score():
    evidence = EntityMatchAssessment(
        entity_id="entity_001",
        score=0.0,
    )

    assert evidence.score == 0.0

#-3-
def test_entity_match_assessment_allows_full_score():
    evidence = EntityMatchAssessment(
        entity_id="entity_001",
        score=1.0,
    )

    assert evidence.score == 1.0

#-4-
def test_entity_match_assessment_rejects_score_above_one():
    with pytest.raises(ValidationError):
        EntityMatchAssessment(
            entity_id="entity_001",
            score=1.1,
        )

#-5-
def test_entity_match_assessment_rejects_negative_score():
    with pytest.raises(ValidationError):
        EntityMatchAssessment(
            entity_id="entity_001",
            score=-0.1,
        )
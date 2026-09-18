import pytest
from pydantic import ValidationError

from app.models import Observation


def test_valid_observation():
    observation = Observation(
        id="obs_001",
        source="photo",
        location="kitchen",
        category="dish_load",
        value=0.82,
        confidence=0.91,
    )

    assert observation.id == "obs_001"
    assert observation.location == "kitchen"
    assert observation.value == 0.82
    assert observation.confidence == 0.91


def test_observation_rejects_invalid_value():
    with pytest.raises(ValidationError):
        Observation(
            id="obs_002",
            source="photo",
            location="kitchen",
            category="dish_load",
            value=2.0,
            confidence=0.91,
        )


def test_observation_rejects_invalid_source():
    with pytest.raises(ValidationError):
        Observation(
            id="obs_003",
            source="random",
            location="kitchen",
            category="dish_load",
            value=0.5,
            confidence=0.91,
        )
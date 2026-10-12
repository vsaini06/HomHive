from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models import ConditionType, Observation, ObservationSource, HouseholdState, TaskDecisionReason
from app.services.reactive_tasks import decide_task_from_observation
from app.services.condition_tracking import build_condition_snapshot, build_household_condition_snapshots
from app.services.state_forecasting import estimate_hourly_change, estimate_forecast_confidence
from app.vision.service import VisionObservationService
from app.vision.provider import VisionCandidate, VisionExtraction


def example_observation(confidence=None, value=0.9, offset=0):
    return Observation(id=f"obs_{offset}", source=ObservationSource.PHOTO, location="kitchen", category=ConditionType.DISH_LOAD, value=value, confidence=confidence, timestamp=datetime(2026, 10, 10, tzinfo=timezone.utc) + timedelta(hours=offset))


def test_unknown_confidence_is_explicit():
    observation = example_observation()
    assert observation.confidence is None
    assert observation.model_dump(mode="json")["confidence"] is None


def test_unknown_confidence_cannot_trigger_task():
    decision = decide_task_from_observation(example_observation())
    assert decision.task is None
    assert decision.reason == TaskDecisionReason.LOW_CONFIDENCE


def test_unknown_confidence_does_not_create_numeric_snapshot():
    known = example_observation(confidence=0.95)
    unknown = example_observation(confidence=None, offset=1)
    with pytest.raises(ValueError, match="Latest observation"):
        build_condition_snapshot([known, unknown])
    state = HouseholdState(id="home")
    state.add_observation(known)
    state.add_observation(unknown)
    assert build_household_condition_snapshots(state) == {}


def test_unknown_confidence_does_not_participate_in_forecasts():
    observations = [example_observation(confidence=0.8), example_observation(offset=1)]
    with pytest.raises(ValueError, match="unknown confidence"):
        estimate_hourly_change(observations)
    with pytest.raises(ValueError, match="unknown-confidence"):
        estimate_forecast_confidence(observations, 2)


def test_vision_service_stores_unknown_confidence_and_provenance():
    class Media:
        def get_image(self, household_id, media_id):
            assert household_id == "home"
            return SimpleNamespace(content_type="image/jpeg"), b"image"

    class Provider:
        def extract(self, image, content_type, location):
            assert location == "kitchen"
            return VisionExtraction(candidates=[VisionCandidate(category=ConditionType.DISH_LOAD, value=1, location="kitchen", visible_evidence="Dirty dishes are visible")], needs_review=False)

    class Store:
        def __init__(self):
            self.items = []

        def add_observation(self, household_id, observation):
            self.items.append((household_id, observation))
            return observation

    store = Store()
    result, created = VisionObservationService(Media(), Provider(), store).extract_and_store("home", "media1", "kitchen")
    assert len(created) == 1
    assert created[0].confidence is None
    assert created[0].metadata == {"media_id": "media1", "visible_evidence": "Dirty dishes are visible"}
    assert store.items[0][0] == "home"


def test_review_required_does_not_persist():
    class Media:
        def get_image(self, household_id, media_id):
            return SimpleNamespace(content_type="image/jpeg"), b"image"

    class Provider:
        def extract(self, image, content_type, location):
            return VisionExtraction(candidates=[], needs_review=True)

    class Store:
        def add_observation(self, household_id, observation):
            raise AssertionError("Should not persist")

    result, created = VisionObservationService(Media(), Provider(), Store()).extract_and_store("home", "media1", "kitchen")
    assert result.needs_review
    assert created == []

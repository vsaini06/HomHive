"""Offline checks for real visual evidence gating and household scene continuity."""
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.coordination.scene_focus import classify_scene_focus
from app.coordination.auto_orchestration import scene_research_topics, research_topic
from app.research.models import ResearchPurpose
from app.services.autonomous_jobs import AutonomousJobService
from app.services.open_world_live import OpenWorldVision, VisualScene


def test_outdoor_lawn_is_space_not_unassigned_plant_object():
    result = classify_scene_focus(["The lawn has visibly tall uneven grass next to a fence"], "Outdoor")
    assert result["focus"] == "space"
    assert not result["location_confirmed"]


def test_demo_laundry_with_washer_no_longer_becomes_unsupported_object_scope():
    result = classify_scene_focus(["Clothes beside a washing machine"], "Laundry", "Laundry")
    assert result["focus"] == "space"
    assert not result["location_confirmed"]


def test_plant_closeup_does_not_infer_an_outdoor_room():
    result = classify_scene_focus(["Close-up of yellow leaves on a plant"], None, "Indoor plants")
    assert result["focus"] == "object"


def test_lawn_research_only_for_reviewed_condition_not_lawn_presence():
    absent = scene_research_topics({"evidence": ["Short green grass is visible near the shed"]})
    assert not any(purpose == ResearchPurpose.MAINTENANCE for purpose, _ in absent)
    present = scene_research_topics({"evidence": ["An outdoor lawn has visibly overgrown uneven grass by the fence"]})
    assert any(purpose == ResearchPurpose.MAINTENANCE for purpose, _ in present)
    task = SimpleNamespace(title="Inspect overgrown lawn", action="Check long grass before mowing",
                           task_payload={"evidence_summary": "Uneven turf visible"})
    assert research_topic(task)[0] == ResearchPurpose.MAINTENANCE


def test_generic_completeness_pass_adds_any_overlooked_claim_for_independent_review():
    calls = []
    class Stub:
        def ask(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return {"room_category": "Outdoor", "claims": [{"id": "e1", "description": "A fence surrounds a patio."}]}
            return {"room_category": "Outdoor", "claims": [
                {"id": "e1", "description": "Grass is visibly tall and uneven beside the patio."},
                {"id": "e2", "description": "A chair is located in the patio."}]}
    vision = OpenWorldVision(Stub(), None)
    scene = vision.extract(b'photo', 'image/jpeg')
    assert len(calls) == 2
    assert [x.id for x in scene.claims] == ['e1', 'e2', 'e3']
    assert 'Grass' in scene.claims[1].description


def test_missing_lawn_does_not_generate_a_lawn_claim():
    class Stub:
        def ask(self, **kwargs):
            return {"room_category": "Outdoor", "claims": [{"id": "e1", "description": "A patio has paving stones."}]}
    scene = OpenWorldVision(Stub(), None).extract(b'photo', 'image/jpeg')
    assert len(scene.claims) == 1


class Media:
    def __init__(self, images): self.images = images
    def get_image(self, home, photo):
        if photo not in self.images: return None
        return SimpleNamespace(content_type='image/jpeg'), self.images[photo]


def _jobs():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    from app.db.base import Base
    Base.metadata.create_all(engine)
    return AutonomousJobService(sessionmaker(engine, expire_on_commit=False))


def _scan(**kwargs):
    return {"status": "reviewed", "room_category": "Laundry", "created": [], "existing": [],
            "review_summary": {"verification": "reviewed"}}


def test_same_photo_reuploaded_uses_unique_existing_room():
    jobs = _jobs()
    jobs.enroll('home', 'first', 'Laundry')
    jobs.enqueue('home', 'again')
    images = Media({'first': b'identical-image', 'again': b'identical-image'})
    calls = []
    with patch('app.vision.autonomous_api.verify_room_pair', side_effect=AssertionError('should not call')):
        assert jobs.process_one(media=images, bridge=None, build_pipeline=lambda: None,
            scan=lambda **kwargs: calls.append(kwargs) or _scan(**kwargs)) == 'completed'
    assert calls[0]['verified_room_evidence'] is True
    assert len(jobs.rooms('home')) == 1


def test_identical_photo_owned_by_two_rooms_is_not_merged():
    jobs = _jobs()
    jobs.enroll('home', 'one', 'Laundry')
    jobs.enroll('home', 'two', 'Laundry')
    jobs.enqueue('home', 'new')
    images = Media({'one': b'identical-image', 'two': b'identical-image', 'new': b'identical-image'})
    assert jobs.process_one(media=images, bridge=None, build_pipeline=lambda: None, scan=_scan) == 'held_unverified_room'
    assert len(jobs.rooms('home')) == 2

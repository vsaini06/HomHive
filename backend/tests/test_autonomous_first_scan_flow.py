from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService
from app.services.autonomous_lifecycle import AutonomousLifecycle
from app.services.autonomous_scan_bridge import AutonomousScanBridge
from app.services.open_world_live import PreviewResult
from app.vision.autonomous_api import run_autonomous_scan


class StoredPhoto:
    def get_image(self, household_id, media_id):
        assert household_id == 'home'
        assert media_id == 'closet-photo'
        return SimpleNamespace(content_type='image/jpeg'), b'closet-image-bytes'


def test_first_scan_creates_real_persisted_task_without_manual_room_enrollment():
    """A mocked reviewed scene exercises the real queue, bridge and database writes."""
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    queue = AutonomousJobService(sessions)
    bridge = AutonomousScanBridge(AutonomousLifecycle(sessions))
    queue.enqueue('home', 'closet-photo')
    reviewed = PreviewResult(
        room_category='walk-in closet',
        corroborated_evidence=[dict(
            id='e1', description='Clothes are visibly scattered across the closet floor',
            provenance='visible', source_id='closet-photo')],
        approved_actions=[dict(
            action_id='organize-floor', title='Organize scattered clothes',
            action='Sort and store garments scattered across the closet floor',
            observation_location='walk-in closet', action_location='walk-in closet',
            supporting_evidence_ids=['e1'], prerequisites=[], assumptions=[],
            verification_criteria='The floor is clear of scattered garments after organizing',
            estimated_effort=None, requires_user_confirmation=False,
            hazard_or_professional_help=False)],
        rejected_actions={}, verification='reviewed')
    independent = SimpleNamespace(client=SimpleNamespace(close=lambda: None))
    vision = SimpleNamespace(independent=independent)
    pipeline = lambda: (vision, object(), object())
    def reviewed_scan(**kwargs):
        return run_autonomous_scan(**kwargs)
    with patch('app.vision.autonomous_api.preview_verified_scene', return_value=reviewed), \
         patch('app.services.effort_research.ground_action_effort', side_effect=lambda action: action.model_copy(update={'estimated_effort': None})):
        state = queue.process_one(media=StoredPhoto(), bridge=bridge,
                                  build_pipeline=pipeline, scan=reviewed_scan)
    assert state == 'completed'
    assert len(queue.rooms('home')) == 1
    assert queue.rooms('home')[0]['room_category'] == 'walk-in closet'
    tasks = bridge.get_tasks('home')
    assert len(tasks) == 1
    assert tasks[0]['title'] == 'Organize scattered clothes'
    assert tasks[0]['room_category'] == 'walk-in closet'
    assert tasks[0]['effort_min'] is None
    assert tasks[0]['created_at']
    assert tasks[0]['status'] == 'pending'


def test_first_scan_with_unverified_room_category_cannot_persist_tasks():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    queue = AutonomousJobService(sessions)
    bridge = AutonomousScanBridge(AutonomousLifecycle(sessions))
    queue.enqueue('home', 'closet-photo')
    reviewed = PreviewResult(room_category=None, corroborated_evidence=[],
                             approved_actions=[], rejected_actions={}, verification='no_corroborated_evidence')
    independent = SimpleNamespace(client=SimpleNamespace(close=lambda: None))
    vision = SimpleNamespace(independent=independent)
    with patch('app.vision.autonomous_api.preview_verified_scene', return_value=reviewed):
        state = queue.process_one(media=StoredPhoto(), bridge=bridge,
            build_pipeline=lambda: (vision, object(), object()), scan=run_autonomous_scan)
    assert state == 'held_unverified_room'
    assert queue.rooms('home') == []
    assert bridge.get_tasks('home') == []

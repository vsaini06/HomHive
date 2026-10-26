from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService
from app.services.autonomous_lifecycle import AutonomousLifecycle
from app.services.autonomous_scan_bridge import AutonomousScanBridge
from app.services.open_world_live import PreviewResult
from app.vision.autonomous_api import build_autonomous_router, run_autonomous_scan


def storage():
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    return engine, factory, AutonomousJobService(factory)


def test_completed_scan_records_zero_task_reason_and_user_room_correction_survives_recheck():
    engine, factory, jobs = storage()
    bridge = AutonomousScanBridge(AutonomousLifecycle(factory))
    jobs.enqueue('owner', 'closet-image')
    media = SimpleNamespace(get_image=lambda *_: (SimpleNamespace(content_type='image/jpeg'), b'photo'))
    vision = SimpleNamespace(independent=SimpleNamespace(client=SimpleNamespace(close=lambda: None)))
    preview = PreviewResult(
        room_category='Laundry Room',
        corroborated_evidence=[{
            'id': 'e1', 'description': 'Several loose clothes cover the closet floor',
            'provenance': 'visible', 'source_id': 'closet-image',
        }],
        approved_actions=[],
        rejected_actions={'proposal1': 'independent_review_rejected_or_missing'},
        verification='reviewed',
        proposed_count=1,
        proposal_reviews=[{
            'title': 'Wash all clothes', 'decision': 'rejected',
            'reason': 'independent_review_rejected_or_missing',
            'reviewer_explanation': 'No visible evidence that these garments are dirty.',
        }],
    )
    with patch('app.vision.autonomous_api.preview_verified_scene', return_value=preview):
        assert jobs.process_one(media=media, bridge=bridge,
            build_pipeline=lambda: (vision, object(), object()), scan=run_autonomous_scan) == 'completed'
    job = jobs.jobs('owner')[0]
    assert job['state'] == 'completed'
    assert job['review_summary']['created_count'] == 0
    assert job['review_summary']['proposed_count'] == 1
    assert job['review_summary']['approved_count'] == 0
    assert 'dirty' in job['review_summary']['proposal_reviews'][0]['reviewer_explanation']
    assert job['review_summary']['evidence'] == ['Several loose clothes cover the closet floor']
    room_id = jobs.rooms('owner')[0]['room_id']
    assert jobs.correct_room_category('owner', room_id, 'Walk-in Closet')['room_category_source'] == 'user_confirmed'
    assert jobs.rooms('owner')[0]['room_category'] == 'Walk-in Closet'
    jobs.set_room_category('owner', room_id, 'Laundry Room')
    assert jobs.rooms('owner')[0]['room_category'] == 'Walk-in Closet'
    assert jobs.recheck_completed('owner', 'closet-image') == job['id']
    assert jobs.jobs('owner')[0]['state'] == 'queued'
    assert jobs.jobs('owner')[0]['review_summary'] == job['review_summary']
    assert jobs.enqueue('owner', 'closet-image') == job['id']
    assert len(jobs.jobs('owner')) == 1
    engine.dispose()


def test_room_correction_and_paid_recheck_require_household_auth_and_scope():
    engine, factory, jobs = storage()
    room_id = jobs.enroll('owner', 'image')
    jid = jobs.enqueue('owner', 'image')
    jobs.finish(jid, 'completed', room_id=room_id)
    media = SimpleNamespace(get_image=lambda *args: (SimpleNamespace(content_type='image/jpeg'), b'photo'))
    app = FastAPI()
    app.include_router(build_autonomous_router(media, {'owner': 'private-token', 'other': 'other-token'},
        factory, build_pipeline=lambda: None, jobs=jobs))
    client = TestClient(app)
    url = '/households/owner/autonomous-rooms/'+room_id+'/category'
    assert client.put(url, json={'room_category': 'Closet'}).status_code == 403
    assert client.put('/households/other/autonomous-rooms/'+room_id+'/category',
        headers={'Authorization': 'Bearer other-token'}, json={'room_category': 'Closet'}).status_code == 404
    assert client.put(url, headers={'Authorization': 'Bearer private-token'},
        json={'room_category': 'Walk-in Closet'}).status_code == 200
    assert jobs.rooms('owner')[0]['room_category_source'] == 'user_confirmed'
    recheck='/households/owner/media/image/autonomous-recheck'
    assert client.post(recheck).status_code == 403
    assert client.post(recheck, headers={'Authorization': 'Bearer private-token'}).status_code == 200
    assert client.post(recheck, headers={'Authorization': 'Bearer private-token'}).status_code == 409
    engine.dispose()

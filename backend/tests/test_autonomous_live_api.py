from types import SimpleNamespace
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from app.vision.autonomous_api import build_autonomous_router, ScanRequest, run_autonomous_scan, review_completion
from app.services.open_world_planning import Evidence
from app.services.autonomous_lifecycle import OutcomeVerdict
from fastapi import FastAPI


def test_autonomous_endpoint_authentication():
    api = FastAPI()
    api.include_router(build_autonomous_router(Mock(), {'home': 'test-secret'}, Mock(), Mock()))
    client = TestClient(api)
    assert client.get('/households/home/autonomous-tasks').status_code == 403
    assert client.post('/households/home/media/picture/autonomous-scan', json={'reference_media_id':'picture'}).status_code == 403


def test_listing_household_scoped():
    factory = Mock()
    api = FastAPI()
    api.include_router(build_autonomous_router(Mock(), {'home': 'secret'}, factory, Mock()))
    client = TestClient(api)
    with patch('app.vision.autonomous_api.AutonomousScanBridge.get_tasks', return_value=[{'id':'task1'}]):
        response = client.get('/households/home/autonomous-tasks', headers={'Authorization':'Bearer secret'})
    assert response.status_code == 200
    assert response.json() == {'tasks':[{'id':'task1'}]}


def test_wrong_room_holds_without_planning_or_writes():
    media = Mock()
    info = SimpleNamespace(content_type='image/jpeg')
    media.get_image.side_effect=[(info,b'reference'),(info,b'current')]
    # Current is requested first, reference second.
    vision=SimpleNamespace(independent=SimpleNamespace(client=Mock()))
    pipeline=Mock(return_value=(vision, Mock(), Mock()))
    bridge=Mock()
    with patch('app.vision.autonomous_api.verify_room_pair', return_value=False):
        result=run_autonomous_scan(household_id='home', media_id='new', reference_media_id='old',
            media=media, bridge=bridge, build_pipeline=pipeline)
    assert result['status']=='held_unverified_room'
    assert result['saved'] is False
    bridge.persist_verified_scan.assert_not_called()
    bridge.reconcile_verified_scan.assert_not_called()


def test_completion_requires_supported_claim_ids():
    reviewer=Mock()
    reviewer.ask.return_value={'verdict':'completed','criterion_verified':True,'claim_ids':['unseen'],
                              'explanation':'The requested task is finished.'}
    evidence=[Evidence(id='e1',description='Clear floor is visible',provenance='visible',source_id='photo2')]
    import pytest
    with pytest.raises(ValueError,match='unsupported'):
        review_completion(reviewer,task={'id':'t1','criteria':'Clear floor'},image=b'photo',
            media_type='image/jpeg',evidence=evidence,media_id='photo2')


def test_completion_review_is_model_verified():
    reviewer=Mock()
    reviewer.ask.return_value={'verdict':'completed','criterion_verified':True,'claim_ids':['e1'],
                              'explanation':'The task-specific floor area is visibly clear.'}
    evidence=[Evidence(id='e1',description='Clear floor is visible',provenance='visible',source_id='photo2')]
    outcome=review_completion(reviewer,task={'id':'t1','criteria':'Clear floor'},image=b'photo',
            media_type='image/jpeg',evidence=evidence,media_id='photo2')
    assert outcome.verdict == OutcomeVerdict.completed
    assert outcome.evidence.media_id == 'photo2'

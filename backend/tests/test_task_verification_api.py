import pytest
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.intelligence import build_intelligence_router
from app.models import ConditionType, Observation, ObservationSource
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.repositories.in_memory_task_repository import InMemoryTaskRepository

HEADERS = {"Authorization": "Bearer secret"}


def setup():
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    app = FastAPI()
    app.include_router(build_intelligence_router(observations, tasks, {"home": "secret", "other": "othersecret"}))
    client = TestClient(app)
    observations.add_observation("home", Observation(id="initial", source=ObservationSource.PHOTO,
        location="kitchen", category=ConditionType.DISH_LOAD, value=0.9, confidence=0.9,
        timestamp=datetime.now(timezone.utc) - timedelta(hours=3)))
    response = client.post('/households/home/intelligence/refresh', headers=HEADERS)
    assert response.status_code == 200
    task = next(t for t in response.json()['tasks'] if t['task_key'] == 'kitchen:dish_load')
    return client, observations, tasks, task['id']


def test_suggestion_inbox_tenant_bound_and_deduped():
    client, _, _, task_id = setup()
    assert client.get('/households/home/suggestions').status_code == 403
    assert client.get('/households/other/suggestions', headers=HEADERS).status_code == 403
    inbox = client.get('/households/home/suggestions', headers=HEADERS)
    assert inbox.status_code == 200
    assert sum(x['task_id'] == task_id for x in inbox.json()) == 1
    assert next(x for x in inbox.json() if x['task_id'] == task_id)['status'] == 'suggested'


def test_done_is_not_verified_and_is_idempotent():
    client, _, tasks, task_id = setup()
    path = f'/households/home/tasks/{task_id}'
    assert client.post(path+'/done', headers=HEADERS, json={}).status_code == 409
    assert client.post(path+'/accept', headers=HEADERS).status_code == 200
    assert client.post(path+'/done', headers=HEADERS, json={'verification_minutes': 1}).status_code == 422
    first = client.post(path+'/done', headers=HEADERS, json={'verification_minutes': 90})
    assert first.status_code == 200
    assert first.json()['status'] == 'pending'
    assert first.json()['metadata']['verification_status'] == 'not_due'
    second = client.post(path+'/done', headers=HEADERS, json={'verification_minutes': 90})
    assert second.json()['metadata']['user_reported_complete_at'] == first.json()['metadata']['user_reported_complete_at']
    assert tasks.find_task('home', task_id).status.value != 'completed'
    assert client.post(path+'/verify', headers=HEADERS).json()['metadata']['verification_status'] == 'not_due'


def _due(client, tasks, task_id):
    task = tasks.find_task('home', task_id)
    task.metadata['verification_due_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    tasks.save_task('home', task)


def _observation(observations, value, confidence=0.95):
    observations.add_observation('home', Observation(id=f'followup-{value}',
        source=ObservationSource.USER_INPUT, location='kitchen',
        category=ConditionType.DISH_LOAD, value=value, confidence=confidence,
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=1)))


def test_missing_fresh_evidence_waits_instead_of_completing():
    client, _, tasks, task_id = setup()
    path = f'/households/home/tasks/{task_id}'
    client.post(path+'/accept', headers=HEADERS)
    client.post(path+'/done', headers=HEADERS, json={})
    _due(client, tasks, task_id)
    response = client.post(path+'/verify', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['metadata']['verification_status'] == 'awaiting_evidence'
    assert response.json()['status'] == 'pending'


def test_fresh_evidence_confirms_resolution_without_duplicate_work():
    client, observations, tasks, task_id = setup()
    path = f'/households/home/tasks/{task_id}'
    client.post(path+'/accept', headers=HEADERS)
    client.post(path+'/done', headers=HEADERS, json={})
    _due(client, tasks, task_id)
    _observation(observations, 0.1)
    response = client.post(path+'/verify', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['metadata']['verification_status'] == 'verified_resolved'
    assert response.json()['status'] == 'completed'
    assert client.post(path+'/verify', headers=HEADERS).json() == response.json()


def test_persistent_condition_does_not_create_new_task():
    client, observations, tasks, task_id = setup()
    path = f'/households/home/tasks/{task_id}'
    client.post(path+'/accept', headers=HEADERS)
    client.post(path+'/done', headers=HEADERS, json={})
    _due(client, tasks, task_id)
    _observation(observations, 0.98)
    response = client.post(path+'/verify', headers=HEADERS)
    assert response.status_code == 200
    assert response.json()['metadata']['verification_status'] == 'verified_persisting'
    assert response.json()['status'] != 'completed'
    client.post('/households/home/intelligence/refresh', headers=HEADERS)
    assert sum(t.task_key == 'kitchen:dish_load' for t in tasks.list_tasks('home')) == 1


@pytest.fixture(autouse=True)
def _use_legacy_intelligence_mode(monkeypatch):
    """Legacy task tests remain deterministic when local autonomous mode is enabled."""
    monkeypatch.setenv("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "false")

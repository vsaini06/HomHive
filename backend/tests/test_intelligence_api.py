import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.intelligence import build_intelligence_router
from app.models import ConditionType, Observation, ObservationSource
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.repositories.in_memory_task_repository import InMemoryTaskRepository


def client_with_storage():
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    app = FastAPI()
    app.include_router(build_intelligence_router(observations, tasks, {"home": "secret"}))
    return TestClient(app), observations, tasks


def test_observation_confirmation_requires_household_token():
    client, observations, _ = client_with_storage()
    observations.add_observation(
        "home",
        Observation(
            id="vision-1",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            value=0.8,
            confidence=None,
        ),
    )

    response = client.post(
        "/households/home/observations/vision-1/confirm",
        json={"confirmed_value": 0.75},
    )

    assert response.status_code == 403


def test_confirmed_observation_can_drive_intelligence_refresh():
    client, observations, _ = client_with_storage()
    observations.add_observation(
        "home",
        Observation(
            id="vision-1",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            value=0.8,
            confidence=None,
        ),
    )
    headers = {"Authorization": "Bearer secret"}

    confirm = client.post(
        "/households/home/observations/vision-1/confirm",
        headers=headers,
        json={"confirmed_value": 0.8},
    )
    refresh = client.post(
        "/households/home/intelligence/refresh",
        headers=headers,
    )

    assert confirm.status_code == 200
    assert refresh.status_code == 200
    body = refresh.json()
    assert body["ranked_tasks"][0]["task"]["task_key"] == "kitchen:dish_load"


def test_autonomous_discovery_and_acceptance_are_persisted_and_idempotent():
    client, observations, tasks = client_with_storage()
    observations.add_observation(
        "home",
        Observation(
            id="vision-accepted",
            source=ObservationSource.PHOTO,
            location="kitchen",
            category=ConditionType.DISH_LOAD,
            value=0.8,
            confidence=None,
        ),
    )
    headers = {"Authorization": "Bearer secret"}
    assert client.post(
        "/households/home/observations/vision-accepted/confirm",
        json={"confirmed_value": 0.8}, headers=headers,
    ).status_code == 200
    report = client.post("/households/home/intelligence/refresh", headers=headers)
    assert report.status_code == 200
    task_id = next(
        item["id"] for item in report.json()["tasks"]
        if item["task_key"] == "kitchen:dish_load"
    )
    assert not tasks.find_task("home", task_id).metadata.get("accepted_at")
    assert client.post(f"/households/home/tasks/{task_id}/accept").status_code == 403
    assert client.post(
        f"/households/other/tasks/{task_id}/accept",
        headers={"Authorization": "Bearer secret"},
    ).status_code == 403
    first = client.post(f"/households/home/tasks/{task_id}/accept", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "pending"
    assert first.json()["metadata"]["accepted_at"]
    second = client.post(f"/households/home/tasks/{task_id}/accept", headers=headers)
    assert second.status_code == 200
    assert second.json()["metadata"]["accepted_at"] == first.json()["metadata"]["accepted_at"]
    assert len([item for item in tasks.list_tasks("home") if item.task_key == "kitchen:dish_load"]) == 1
    assert client.post("/households/home/tasks/missing/accept", headers=headers).status_code == 404


def test_proposal_defer_dismiss_and_refresh_preserve_human_decisions():
    client, observations, tasks = client_with_storage()
    observations.add_observation("home", Observation(
        id="vision-lifecycle", source=ObservationSource.PHOTO,
        location="kitchen", category=ConditionType.DISH_LOAD,
        value=0.8, confidence=0.9,
    ))
    headers = {"Authorization": "Bearer secret"}
    first = client.post("/households/home/intelligence/refresh", headers=headers)
    assert first.status_code == 200
    items = first.json()["ranked_tasks"]
    assert len([t for t in items if t["task"]["task_key"].endswith("kitchen:dish_load")]) == 1
    task_id = next(t["task"]["id"] for t in items if t["task"]["task_key"] == "kitchen:dish_load")
    assert client.post(f"/households/home/tasks/{task_id}/defer", headers=headers, json={"minutes": 0}).status_code == 422
    assert client.post(f"/households/home/tasks/{task_id}/defer", json={"minutes": 60}).status_code == 403
    deferred = client.post(f"/households/home/tasks/{task_id}/defer", headers=headers, json={"minutes": 60})
    assert deferred.status_code == 200
    assert deferred.json()["metadata"]["deferred_until"]
    after = client.post("/households/home/intelligence/refresh", headers=headers).json()
    assert task_id not in [t["task"]["id"] for t in after["ranked_tasks"]]
    assert tasks.find_task("home", task_id).metadata.get("deferred_until")
    dismissed = client.post(f"/households/home/tasks/{task_id}/dismiss", headers=headers)
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"
    assert client.post(f"/households/home/tasks/{task_id}/dismiss", headers=headers).status_code == 200
    after = client.post("/households/home/intelligence/refresh", headers=headers).json()
    assert task_id not in [t["task"]["id"] for t in after["ranked_tasks"]]
    assert tasks.find_task("home", task_id).status.value == "dismissed"


def test_accepted_task_cannot_be_deferred_or_dismissed():
    client, observations, tasks = client_with_storage()
    observations.add_observation("home", Observation(
        id="vision-committed", source=ObservationSource.PHOTO,
        location="kitchen", category=ConditionType.DISH_LOAD,
        value=0.8, confidence=0.9,
    ))
    headers = {"Authorization": "Bearer secret"}
    result = client.post("/households/home/intelligence/refresh", headers=headers).json()
    task_id = next(t["task"]["id"] for t in result["ranked_tasks"] if t["task"]["task_key"] == "kitchen:dish_load")
    assert client.post(f"/households/home/tasks/{task_id}/accept", headers=headers).status_code == 200
    assert client.post(f"/households/home/tasks/{task_id}/defer", headers=headers, json={"minutes": 60}).status_code == 409
    assert client.post(f"/households/home/tasks/{task_id}/dismiss", headers=headers).status_code == 409


def test_observation_history_is_household_scoped_and_persistent():
    client, observations, _ = client_with_storage()
    observations.add_observation("home", Observation(
        id="history-1", source=ObservationSource.PHOTO,
        location="kitchen", category=ConditionType.DISH_LOAD,
        value=0.76, confidence=None, metadata={"visible_evidence": "Dishes"},
    ))
    observations.add_observation("other", Observation(
        id="private-1", source=ObservationSource.PHOTO,
        location="bedroom", category=ConditionType.LAUNDRY_LOAD,
        value=0.2, confidence=0.8,
    ))
    url = "/households/home/observations"
    assert client.get(url).status_code == 403
    assert client.get(url, headers={"Authorization": "Bearer wrong"}).status_code == 403
    response = client.get(url, headers={"Authorization": "Bearer secret"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == "history-1"
    assert response.json()[0]["timestamp"]
    assert response.json()[0]["metadata"]["visible_evidence"] == "Dishes"


@pytest.fixture(autouse=True)
def _use_legacy_intelligence_mode(monkeypatch):
    """Legacy task tests remain deterministic when local autonomous mode is enabled."""
    monkeypatch.setenv("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "false")

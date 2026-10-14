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

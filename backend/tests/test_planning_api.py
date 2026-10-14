from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models import Task, TaskUrgency
from app.planning.api import build_planning_router
from app.planning.service import PlanningService
from app.repositories.in_memory_task_repository import InMemoryTaskRepository


def test_planning_endpoint_returns_deterministic_fallback():
    storage = InMemoryTaskRepository()
    storage.add_task(
        "home",
        Task(
            id="dish-task",
            task_key="kitchen:dish_load",
            description="Clear the dishes",
            urgency=TaskUrgency.MEDIUM,
            estimated_effort_minutes=15,
            confidence=0.9,
        ),
    )
    app = FastAPI()
    app.include_router(
        build_planning_router(
            PlanningService(storage),
            {"home": "secret"},
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/households/home/plan",
            headers={"Authorization": "Bearer secret"},
            json={
                "context": {
                    "available_minutes": 20,
                    "at_home": True,
                    "quiet_hours_active": False,
                    "max_tasks": 5,
                },
                "research": [],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["planner"] == "deterministic"
    assert body["plan"]["steps"][0]["task_id"] == "dish-task"


def test_planning_endpoint_rejects_wrong_household_token():
    app = FastAPI()
    app.include_router(
        build_planning_router(
            PlanningService(InMemoryTaskRepository()),
            {"home": "secret"},
        )
    )

    with TestClient(app) as client:
        response = client.post(
            "/households/home/plan",
            headers={"Authorization": "Bearer wrong"},
            json={
                "context": {
                    "available_minutes": 20,
                    "at_home": True,
                    "quiet_hours_active": False,
                }
            },
        )

    assert response.status_code == 403

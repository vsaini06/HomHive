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
            metadata={"accepted_at": "2026-10-21T10:00:00+00:00"},
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


def test_plan_excludes_unaccepted_duplicates_and_deferred_work():
    from datetime import datetime, timedelta, timezone
    from app.models import TaskStatus

    storage = InMemoryTaskRepository()
    def add(identifier, key, metadata=None, status=TaskStatus.PENDING):
        storage.add_task("home", Task(
            id=identifier, task_key=key, description=identifier,
            urgency=TaskUrgency.MEDIUM, estimated_effort_minutes=15,
            confidence=0.9, status=status, metadata=metadata or {},
        ))

    add("observed", "kitchen:dish_load", {"accepted_at": "2026-10-21T10:00:00+00:00"})
    add("forecast", "predictive:kitchen:dish_load")
    add("unaccepted", "bathroom:laundry_load")
    add("dismissed", "bedroom:laundry_load", status=TaskStatus.DISMISSED)
    add("deferred", "garage:lawn_condition", {
        "accepted_at": "2026-10-21T10:00:00+00:00",
        "deferred_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    })
    plan, feasibility, _ = PlanningService(storage).create_plan(
        "home", __import__("app.planning", fromlist=["PlanningContext"]).PlanningContext(available_minutes=60)
    )
    assert [step.task_id for step in plan.steps] == ["observed"]
    assert [item.task_id for item in feasibility] == ["observed"]


def test_plan_deduplicates_even_two_accepted_equivalent_tasks():
    from app.planning import PlanningContext
    storage = InMemoryTaskRepository()
    for identifier, key in [("observed", "kitchen:dish_load"), ("forecast", "predictive:kitchen:dish_load")]:
        storage.add_task("home", Task(
            id=identifier, task_key=key, description=identifier,
            urgency=TaskUrgency.MEDIUM, estimated_effort_minutes=15,
            confidence=0.9, metadata={"accepted_at": "2026-10-21T10:00:00+00:00"},
        ))
    plan, _, _ = PlanningService(storage).create_plan("home", PlanningContext(available_minutes=30))
    assert [step.task_id for step in plan.steps] == ["observed"]

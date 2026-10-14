from datetime import datetime, timedelta, timezone

from app.models import ConditionType, Observation, ObservationSource, TaskStatus
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.services.household_intelligence import refresh_household_intelligence


def observation(identifier, value, confidence, timestamp):
    return Observation(
        id=identifier,
        source=ObservationSource.USER_INPUT,
        location="kitchen",
        category=ConditionType.DISH_LOAD,
        value=value,
        confidence=confidence,
        timestamp=timestamp,
    )


def test_refresh_creates_reactive_task_from_confirmed_current_observation():
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    observations.add_observation(
        "home",
        observation("one", 0.8, 1.0, datetime.now(timezone.utc)),
    )

    report = refresh_household_intelligence("home", observations, tasks)

    assert any(task.task_key == "kitchen:dish_load" for task in report.tasks)
    assert report.ranked_tasks


def test_refresh_does_not_create_reactive_task_from_unknown_confidence():
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    observations.add_observation(
        "home",
        observation("one", 0.9, None, datetime.now(timezone.utc)),
    )

    report = refresh_household_intelligence("home", observations, tasks)

    assert report.tasks == []
    assert report.snapshots == []


def test_refresh_is_idempotent_for_active_reactive_task():
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    observations.add_observation(
        "home",
        observation("one", 0.9, 1.0, datetime.now(timezone.utc)),
    )

    refresh_household_intelligence("home", observations, tasks)
    refresh_household_intelligence("home", observations, tasks)

    active = [task for task in tasks.list_tasks("home") if task.status == TaskStatus.PENDING]
    assert len([task for task in active if task.task_key == "kitchen:dish_load"]) == 1


def test_refresh_builds_forecast_from_persisted_history():
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    now = datetime.now(timezone.utc)
    observations.add_observation("home", observation("one", 0.2, 0.9, now - timedelta(hours=4)))
    observations.add_observation("home", observation("two", 0.5, 0.9, now))

    report = refresh_household_intelligence("home", observations, tasks)

    assert len(report.forecasts) == 1
    assert report.forecasts[0].rate_per_hour > 0

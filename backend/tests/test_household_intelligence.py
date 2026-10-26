import pytest
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


def test_refresh_advances_overdue_completion_without_fabricating_resolution():
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    now = datetime.now(timezone.utc)
    observations.add_observation('home', observation('source', 0.88, 0.95, now - timedelta(hours=4)))
    first = refresh_household_intelligence('home', observations, tasks)
    task = next(item for item in first.tasks if item.task_key == 'kitchen:dish_load')
    task.metadata.update({
        'accepted_at': (now - timedelta(hours=2)).isoformat(),
        'user_reported_complete_at': (now - timedelta(hours=1)).isoformat(),
        'verification_due_at': (now - timedelta(minutes=1)).isoformat(),
        'verification_status': 'not_due',
        'verification_attempts': 0,
    })
    tasks.save_task('home', task)
    refresh_household_intelligence('home', observations, tasks)
    updated = tasks.find_task('home', task.id)
    assert updated.metadata['verification_status'] == 'awaiting_evidence'
    assert updated.metadata['verification_attempts'] == 1
    assert updated.status == TaskStatus.PENDING
    refresh_household_intelligence('home', observations, tasks)
    assert tasks.find_task('home', task.id).metadata['verification_attempts'] == 1


def test_refresh_keeps_not_yet_due_verification_intact():
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    now = datetime.now(timezone.utc)
    observations.add_observation('home', observation('source', 0.88, 0.95, now - timedelta(hours=2)))
    task = next(item for item in refresh_household_intelligence('home', observations, tasks).tasks if item.task_key == 'kitchen:dish_load')
    task.metadata.update({
        'user_reported_complete_at': now.isoformat(),
        'verification_due_at': (now + timedelta(hours=1)).isoformat(),
        'verification_status': 'not_due',
        'verification_attempts': 0,
    })
    tasks.save_task('home', task)
    refresh_household_intelligence('home', observations, tasks)
    assert tasks.find_task('home', task.id).metadata['verification_status'] == 'not_due'
    assert tasks.find_task('home', task.id).metadata['verification_attempts'] == 0


def test_autonomous_queue_disables_preset_photo_chore_discovery(monkeypatch):
    monkeypatch.setenv("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "true")
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    observations.add_observation(
        "home", observation("closet-photo", 0.95, 0.99, datetime.now(timezone.utc))
    )
    report = refresh_household_intelligence("home", observations, tasks)
    assert report.tasks == []
    assert report.state.current_observations


def test_autonomous_queue_preserves_existing_legacy_tasks(monkeypatch):
    observations = InMemoryObservationRepository()
    tasks = InMemoryTaskRepository()
    observations.add_observation(
        "home", observation("existing-photo", 0.9, 1.0, datetime.now(timezone.utc))
    )
    previous = refresh_household_intelligence("home", observations, tasks)
    assert len(previous.tasks) == 1
    monkeypatch.setenv("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "true")
    report = refresh_household_intelligence("home", observations, tasks)
    assert len(report.tasks) == 1
    assert report.tasks[0].id == previous.tasks[0].id


@pytest.fixture(autouse=True)
def _use_legacy_intelligence_mode(monkeypatch):
    """Legacy task tests remain deterministic when local autonomous mode is enabled."""
    monkeypatch.setenv("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "false")

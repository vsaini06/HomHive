import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.automation.worker import run_due
from app.db.base import Base
from app.db.task_record import TaskRecord
from app.db.notification_record import NotificationRecord
from app.db.observation_record import ObservationRecord
from app.models import ConditionType, Observation, ObservationSource
from app.repositories.sqlalchemy_observation_repository import SQLAlchemyObservationRepository
from app.repositories.sqlalchemy_task_repository import SQLAlchemyTaskRepository
from app.services.household_intelligence import refresh_household_intelligence


def prepare(tmp_path):
    engine = create_engine(f'sqlite+pysqlite:///{tmp_path / "worker.sqlite"}')
    Base.metadata.create_all(engine, tables=[TaskRecord.__table__, ObservationRecord.__table__, NotificationRecord.__table__])
    sessions = sessionmaker(engine, expire_on_commit=False)
    observations = SQLAlchemyObservationRepository(sessions)
    tasks = SQLAlchemyTaskRepository(sessions)
    now = datetime.now(timezone.utc)
    observations.add_observation('household-a', Observation(
        id='trigger', source=ObservationSource.USER_INPUT, location='kitchen',
        category=ConditionType.DISH_LOAD, value=0.9, confidence=0.95,
        timestamp=now - timedelta(hours=2)))
    refresh_household_intelligence('household-a', observations, tasks)
    task = next(item for item in tasks.list_tasks('household-a') if item.task_key == 'kitchen:dish_load')
    task.metadata = {**task.metadata,
        'accepted_at': (now-timedelta(hours=1)).isoformat(),
        'user_reported_complete_at': (now-timedelta(minutes=30)).isoformat(),
        'verification_due_at': (now-timedelta(minutes=5)).isoformat(),
        'verification_attempts': 0, 'verification_status': 'not_due'}
    tasks.save_task('household-a', task)
    return engine, sessions, observations, tasks, task.id, now


def test_worker_survives_recreation_and_never_assumes_no_evidence_means_done(tmp_path):
    engine, sessions, observations, tasks, task_id, now = prepare(tmp_path)
    first = run_due(sessions, now=now)
    assert first['checked'] == first['needs_evidence'] == 1
    task = tasks.find_task('household-a', task_id)
    assert task.metadata['verification_status'] == 'awaiting_evidence'
    assert task.status.value == 'pending'
    assert run_due(sessionmaker(engine, expire_on_commit=False), now=now)['checked'] == 0
    assert len(tasks.list_tasks('household-a')) == 1
    engine.dispose()


def test_worker_marks_fresh_resolved_evidence_and_prevents_duplicate_work(tmp_path):
    engine, sessions, observations, tasks, task_id, now = prepare(tmp_path)
    observations.add_observation('household-a', Observation(
        id='followup', source=ObservationSource.USER_INPUT, location='kitchen',
        category=ConditionType.DISH_LOAD, value=0.1, confidence=0.95,
        timestamp=now-timedelta(minutes=10)))
    report = run_due(sessions, now=now)
    assert report['resolved'] == 1
    assert tasks.find_task('household-a', task_id).status.value == 'completed'
    assert run_due(sessions, now=now)['checked'] == 0
    engine.dispose()


def test_worker_keeps_persisting_issue_unresolved(tmp_path):
    engine, sessions, observations, tasks, task_id, now = prepare(tmp_path)
    observations.add_observation('household-a', Observation(
        id='followup', source=ObservationSource.USER_INPUT, location='kitchen',
        category=ConditionType.DISH_LOAD, value=0.95, confidence=0.95,
        timestamp=now-timedelta(minutes=10)))
    report = run_due(sessions, now=now)
    assert report['persisting'] == 1
    assert tasks.find_task('household-a', task_id).status.value == 'pending'
    assert len(tasks.list_tasks('household-a')) == 1
    engine.dispose()


@pytest.fixture(autouse=True)
def _use_legacy_intelligence_mode(monkeypatch):
    """Legacy task tests remain deterministic when local autonomous mode is enabled."""
    monkeypatch.setenv("HOMHIVE_ENABLE_AUTONOMOUS_QUEUE", "false")

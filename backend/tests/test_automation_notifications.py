from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.automation.api import build_automation_router
from app.automation.context import (Feasibility, household_feasibility,
                                    PresenceState, current_presence)
from app.automation.worker import run_due
from app.db.base import Base
from app.db.notification_record import NotificationRecord
from app.db.presence_record import PresenceRecord
from app.db.task_record import TaskRecord
from app.models import Task, TaskUrgency
from app.repositories.sqlalchemy_task_repository import SQLAlchemyTaskRepository


def setup(tmp_path):
    engine = create_engine(f'sqlite+pysqlite:///{tmp_path / "automation.db"}')
    Base.metadata.create_all(engine, tables=[TaskRecord.__table__, NotificationRecord.__table__, PresenceRecord.__table__])
    sessions = sessionmaker(engine, expire_on_commit=False)
    tasks = SQLAlchemyTaskRepository(sessions)
    tasks.add_task('a', Task(id='task1', task_key='kitchen:dish_load', description='Clear the dishes',
        urgency=TaskUrgency.MEDIUM, estimated_effort_minutes=15, confidence=0.8))
    app=FastAPI()
    app.include_router(build_automation_router(sessions, {'a':'secret', 'b':'other'}))
    return engine, sessions, tasks, TestClient(app)


def test_notifications_are_durable_deduped_and_tenant_isolated(tmp_path):
    engine, sessions, tasks, client=setup(tmp_path)
    assert client.get('/households/a/notifications').status_code == 403
    first=client.get('/households/a/notifications', headers={'Authorization':'Bearer secret'})
    assert first.status_code == 200 and len(first.json()) == 1
    assert first.json()[0]['title'] == 'Clear the dishes'
    assert first.json()[0]['feasibility'] == 'UNKNOWN'
    assert first.json()[0]['recommended_time'] is None
    assert run_due(sessions)['notifications_created'] == 0
    assert client.get('/households/b/notifications', headers={'Authorization':'Bearer other'}).json() == []
    assert len(client.get('/households/a/notifications', headers={'Authorization':'Bearer secret'}).json()) == 1
    task=tasks.find_task('a','task1');task.metadata={'deferred_until':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
    tasks.save_task('a',task)
    assert client.get('/households/a/notifications', headers={'Authorization':'Bearer secret'}).json() == []
    engine.dispose()


def test_presence_requires_consent_expires_and_does_not_mean_available(tmp_path):
    engine, sessions, _, client=setup(tmp_path)
    h={'Authorization':'Bearer secret'}
    assert client.get('/households/a/presence', headers=h).json()['state'] == 'UNKNOWN'
    response=client.post('/households/a/presence',headers=h,
        json={'state':'HOME','consent':True,'ttl_minutes':10})
    assert response.status_code == 200 and response.json()['state'] == 'HOME'
    assert household_feasibility('HOME') == Feasibility.UNKNOWN
    assert household_feasibility('AWAY') == Feasibility.NOT_FEASIBLE
    later=datetime.now(timezone.utc)+timedelta(minutes=11)
    assert current_presence(sessions,'a',later)['state'] == 'UNKNOWN'
    assert client.post('/households/a/presence/revoke',headers=h).json()['state'] == 'UNKNOWN'
    assert client.get('/households/a/presence',headers=h).json()['consent'] is False
    assert client.post('/households/a/presence',headers={'Authorization':'Bearer other'},
        json={'state':'HOME','consent':True}).status_code == 403
    engine.dispose()

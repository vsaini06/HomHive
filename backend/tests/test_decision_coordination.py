from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.presence_record import PresenceRecord
from app.services.autonomous_lifecycle import AutonomousAvailabilityRecord, AutonomousTaskRecord
from app.coordination.models import ContextSignalRecord, QuietHoursRecord
from app.coordination.service import (
    set_availability, availability_status, set_quiet_hours, quiet_hours_active,
    coordination_plan,
)

NOW = datetime(2026, 10, 27, 19, 15, tzinfo=timezone.utc)


def storage():
    engine = create_engine('sqlite+pysqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def seed(sessions):
    with sessions.begin() as db:
        db.add(PresenceRecord(household_id='a', signal_source='manual', state='HOME',
            reliability=1, consent_granted=True, updated_at=NOW, expires_at=NOW+timedelta(hours=2)))
        db.add(AutonomousAvailabilityRecord(household_id='a', timezone='UTC',
            start_time='18:00', end_time='21:00', weekdays=[0,1,2,3,4,5,6], updated_at=NOW))
        db.add(AutonomousTaskRecord(household_id='a', id='task-1', physical_room_id='ref:photo',
            action_key='closet_work', title='Review closet floor', action='Review visible items',
            criteria='Visible floor is clear', state='pending', effort_min=10, effort_max=15,
            task_payload={'estimate_sources':['https://a.example/1','https://b.example/2'],
                'noise_level':'quiet', 'confirmation_required':False},
            created_at=NOW, updated_at=NOW))


def test_dynamic_replanning_respects_presence_and_availability_expiry():
    engine, db = storage()
    seed(db)
    set_availability(db, 'a', 'FREE', ttl_minutes=90, now=NOW)
    plan = coordination_plan(db, 'a', NOW)
    assert plan['groups']['NOW'] == 1
    assert plan['tasks'][0]['duration_max'] == 15
    assert plan['tasks'][0]['source'] == 'corroborated_household_evidence'
    with db.begin() as session:
        presence = session.get(PresenceRecord, 'a')
        presence.state = 'AWAY'
    away = coordination_plan(db, 'a', NOW)
    assert away['tasks'][0]['status'] == 'BLOCKED'
    assert 'away' in away['tasks'][0]['reasons'][0]
    with db.begin() as session:
        session.get(PresenceRecord, 'a').state = 'HOME'
    assert coordination_plan(db, 'a', NOW+timedelta(minutes=91))['tasks'][0]['status'] == 'SOON'
    assert coordination_plan(db, 'b', NOW)['tasks'] == []
    engine.dispose()


def test_manual_busy_blocks_current_work_and_unknown_is_not_free():
    engine, db = storage(); seed(db)
    assert coordination_plan(db,'a',NOW)['tasks'][0]['status'] == 'SOON'
    set_availability(db,'a','BUSY',now=NOW)
    assert coordination_plan(db,'a',NOW)['tasks'][0]['status'] == 'DEFERRED'
    set_availability(db,'a','UNKNOWN',now=NOW)
    assert availability_status(db,'a',NOW)['state'] == 'UNKNOWN'
    engine.dispose()


def test_quiet_hours_with_unknown_noise_defers_but_inactive_is_not_fake_availability():
    engine, db = storage(); seed(db)
    set_availability(db,'a','FREE',now=NOW)
    with db.begin() as session:
        t = session.get(AutonomousTaskRecord, ('a','task-1'))
        t.task_payload = {**t.task_payload, 'noise_level':'unknown'}
    set_quiet_hours(db,'a',True,'19:00','07:00',now=NOW)
    p=coordination_plan(db,'a',NOW)
    assert p['quiet_hours']['active'] is True and p['tasks'][0]['status'] == 'DEFERRED'
    set_quiet_hours(db,'a',False,'19:00','07:00',now=NOW)
    assert coordination_plan(db,'a',NOW)['tasks'][0]['status'] == 'NOW'
    assert quiet_hours_active(datetime(2026,10,27,23,0),enabled=True,start='22:00',end='07:00')
    assert quiet_hours_active(datetime(2026,10,28,2,0),enabled=True,start='22:00',end='07:00')
    assert not quiet_hours_active(datetime(2026,10,28,12,0),enabled=True,start='22:00',end='07:00')
    engine.dispose()


def test_ungrounded_duration_does_not_claim_schedule_fit():
    engine, db = storage(); seed(db)
    set_availability(db,'a','FREE',now=NOW)
    with db.begin() as session:
        t = session.get(AutonomousTaskRecord, ('a','task-1'))
        t.task_payload = {**t.task_payload, 'estimate_sources': []}
    p = coordination_plan(db,'a',NOW)
    assert p['tasks'][0]['status'] == 'SOON'
    assert p['tasks'][0]['duration_max'] is None
    engine.dispose()


def test_cross_household_isolation_and_completed_excluded():
    engine, db=storage();seed(db)
    set_availability(db,'a','FREE',now=NOW)
    assert availability_status(db,'b',NOW)['state']=='UNKNOWN'
    assert coordination_plan(db,'b',NOW)['groups']['NOW']==0
    with db.begin() as session:
        session.get(AutonomousTaskRecord,('a','task-1')).state='completed'
    assert coordination_plan(db,'a',NOW)['tasks']==[]
    engine.dispose()


def test_authenticated_coordination_api_is_household_scoped():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.coordination.api import build_coordination_router
    engine, sessions = storage()
    seed(sessions)
    app = FastAPI()
    app.include_router(build_coordination_router(sessions, {'a': 'secret-a', 'b': 'secret-b'}))
    client = TestClient(app)
    route = '/households/a/coordination'
    assert client.get(route).status_code == 403
    assert client.get(route, headers={'Authorization': 'Bearer secret-b'}).status_code == 403
    headers={'Authorization':'Bearer secret-a'}
    assert client.get(route, headers=headers).status_code == 200
    changed = client.put(route+'/availability', headers=headers,
        json={'state': 'BUSY', 'ttl_minutes': 60})
    assert changed.status_code == 200
    assert changed.json()['availability']['state'] == 'BUSY'
    assert client.put(route+'/availability', headers=headers,
        json={'state': 'AVAILABLE_FOREVER'}).status_code == 422
    assert client.put(route+'/quiet-hours', headers=headers,
        json={'enabled': True, 'start_time': '22:00', 'end_time': '07:00'}).status_code == 200
    assert client.get('/households/b/coordination', headers={'Authorization':'Bearer secret-b'}).json()['availability']['state']=='UNKNOWN'
    engine.dispose()


def test_quiet_hours_respects_household_time_zone_without_work_schedule():
    engine, sessions = storage()

    moment = datetime(2026, 10, 27, 6, 30, tzinfo=timezone.utc)
    result = set_quiet_hours(sessions, 'a', True, '22:00', '07:00', now=moment,
                             timezone_name='America/Phoenix')
    assert result['timezone'] == 'America/Phoenix'
    plan = coordination_plan(sessions, 'a', moment)
    assert plan['timezone'] == 'America/Phoenix'
    assert plan['quiet_hours']['active'] is True
    assert plan['quiet_hours']['timezone'] == 'America/Phoenix'
    assert coordination_plan(sessions, 'a', moment + timedelta(hours=10))['quiet_hours']['active'] is False
    engine.dispose()


def test_accepted_suggestion_not_blocked_by_stale_approval_flag():
    engine, sessions = storage()
    seed(sessions)
    with sessions.begin() as session:
        t = session.get(AutonomousTaskRecord, ('a', 'task-1'))
        t.task_payload = {**t.task_payload, 'confirmation_required': True}
    set_availability(sessions, 'a', 'FREE', ttl_minutes=90, now=NOW)
    assert coordination_plan(sessions, 'a', NOW)['tasks'][0]['status'] == 'BLOCKED'
    with sessions.begin() as session:
        session.get(AutonomousTaskRecord, ('a', 'task-1')).state = 'accepted'
    assert coordination_plan(sessions, 'a', NOW)['tasks'][0]['status'] == 'NOW'
    engine.dispose()


def test_quiet_hours_api_validates_timezones_and_household_isolation():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.coordination.api import build_coordination_router
    engine, sessions = storage()
    app = FastAPI()
    app.include_router(build_coordination_router(sessions, {'a':'secret-a','b':'secret-b'}))
    client = TestClient(app)
    url = '/households/a/coordination/quiet-hours'
    auth = {'Authorization':'Bearer secret-a'}
    bad = {'enabled': True, 'start_time':'22:07', 'end_time':'07:23','timezone':'Fake/Nowhere'}
    assert client.put(url, json=bad, headers=auth).status_code == 422
    bad['timezone'] = 'America/Phoenix'
    assert client.put(url, json=bad, headers={'Authorization':'Bearer secret-b'}).status_code == 403
    response = client.put(url, json=bad, headers=auth)
    assert response.status_code == 200
    assert response.json()['quiet_hours']['timezone'] == 'America/Phoenix'
    assert response.json()['quiet_hours']['start_time'] == '22:07'
    assert response.json()['quiet_hours']['end_time'] == '07:23'
    assert client.get('/households/b/coordination', headers={'Authorization':'Bearer secret-b'}).json()['quiet_hours']['timezone'] == 'UTC'
    engine.dispose()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService

def test_enroll_enqueue_and_claim():
    e=create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(e)
    jobs=AutonomousJobService(sessionmaker(e, expire_on_commit=False))
    assert jobs.enroll('h','m') == jobs.enroll('h','m')
    assert len(jobs.rooms('h')) == 1
    jid=jobs.enqueue('h','m')
    assert jobs.enqueue('h','m')==jid
    job=jobs.claim()
    assert job['id']==jid and job['attempts']==1
    jobs.finish(jid,'completed',room_id='reference:m')
    assert jobs.jobs('h')[0]['state']=='completed'
    assert jobs.claim() is None

def test_no_enrolled_room_holds_unassigned_media():
    e=create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(e)
    jobs=AutonomousJobService(sessionmaker(e,expire_on_commit=False))
    jobs.enqueue('h','m')
    class Media: pass
    result=jobs.process_one(media=Media(),bridge=None,build_pipeline=None,scan=None)
    assert result == 'held_unverified_room'
    assert jobs.jobs('h')[0]['state']=='held_unverified_room'

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService
from app.services.autonomous_lifecycle import (
    AutonomousLifecycle, EvidenceReference, RoomContinuity, TaskState, VerifiedAction,
    AutonomousTaskRecord,
)


def services():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    return AutonomousJobService(sessions), AutonomousLifecycle(sessions), sessions


def action(media, title, action_key):
    return VerifiedAction(
        action_key=action_key, title=title, action='Wash dirty dishes from the sink',
        verification_criteria='Dirty dishes in the sink are cleaned and removed',
        evidence=EvidenceReference(media_id=media, claim_ids=['e1'],
            original_image_reviewed=True, independent_review_passed=True),
    )


def room(room_id='reference:sink'):
    return RoomContinuity(physical_room_id=room_id, same_physical_room_verified=True,
        reason='A user confirmed physical room identity')


def test_similar_tasks_in_same_room_share_one_record():
    _, lifecycle, _ = services()
    first = lifecycle.discover('home', room(), [action('a', 'Wash dirty dishes in the sink', 'wash-dishes-1')])
    second = lifecycle.discover('home', room(), [action('b', 'Wash dirty dishes, pots and utensils in the sink', 'wash-dishes-2')])
    assert second['created'] == [] and second['existing'] == first['created']
    assert len(lifecycle.list_tasks('home')) == 1


def test_different_rooms_and_distinct_work_are_preserved():
    _, lifecycle, _ = services()
    lifecycle.discover('home', room(), [action('a', 'Wash dirty dishes in the sink', 'wash-task-1')])
    lifecycle.discover('home', room('reference:other'), [action('b', 'Wash dirty dishes in the sink', 'wash-task-2')])
    lifecycle.discover('home', room(), [action('c', 'Sweep the kitchen floor', 'sweep-floor')])
    assert len(lifecycle.list_tasks('home')) == 3


def test_new_evidence_can_start_new_task_cycle_after_verified_completion():
    _, lifecycle, sessions = services()
    initial = lifecycle.discover('home', room(), [action('dirty-1', 'Wash dirty dishes in the sink', 'wash-dishes')])
    with sessions.begin() as db:
        task = db.get(AutonomousTaskRecord, ('home', initial['created'][0]))
        task.state = TaskState.completed.value
    later = lifecycle.discover('home', room(), [action('dirty-2', 'Wash dirty dishes in the sink', 'wash-dishes')])
    repeat = lifecycle.discover('home', room(), [action('dirty-2', 'Wash dirty dishes in the sink', 'wash-dishes')])
    assert len(later['created']) == 1
    assert repeat['existing'] == later['created']
    assert len(lifecycle.list_tasks('home')) == 2
    with sessions() as db:
        rows = db.query(AutonomousTaskRecord).filter_by(household_id='home').all()
        assert len({row.action_key for row in rows}) == 2


def test_unverified_room_can_be_assigned_only_by_household_member():
    jobs, _, _ = services()
    jobs.enroll('home', 'reference-photo')
    jid = jobs.enqueue('home', 'follow-up')
    jobs.finish(jid, 'held_unverified_room', 'No unique verified room match')
    with pytest.raises(LookupError):
        jobs.assign_existing_room('different', 'follow-up', 'reference:reference-photo')
    with pytest.raises(LookupError):
        jobs.assign_existing_room('home', 'follow-up', 'reference:someone-else')
    result = jobs.assign_existing_room('home', 'follow-up', 'reference:reference-photo')
    assert result == {'room_id': 'reference:reference-photo', 'job_id': jid}
    assert jobs.jobs('home')[0]['state'] == 'queued'
    with pytest.raises(ValueError):
        jobs.assign_existing_room('home', 'follow-up', 'reference:reference-photo')


def test_user_confirmed_room_skips_model_identity_guess_but_is_recorded():
    jobs, _, _ = services()
    jobs.enroll('home', 'original')
    jid = jobs.enqueue('home', 'follow-up')
    jobs.finish(jid, 'held_unverified_room', 'No unique verified room match')
    jobs.assign_existing_room('home', 'follow-up', 'reference:original')

    class Media:
        def get_image(self, household_id, media_id):
            assert household_id == 'home'
            return SimpleNamespace(content_type='image/jpeg'), media_id.encode()

    captured = []
    def scan(**kwargs):
        captured.append(kwargs)
        return {'status': 'reviewed', 'created': [], 'existing': [],
                'room_category': 'kitchen', 'review_summary': {'room_identity_source': 'user_confirmed'}}

    with patch('app.vision.autonomous_api.verify_room_pair', side_effect=AssertionError('Must not guess identity')):
        result = jobs.process_one(media=Media(), bridge=object(), build_pipeline=lambda: None, scan=scan)
    assert result == 'completed'
    assert captured[0]['user_confirmed_room'] is True
    assert captured[0]['reference_media_id'] == 'original'
    assert jobs.jobs('home')[0]['review_summary']['room_identity_source'] == 'user_confirmed'

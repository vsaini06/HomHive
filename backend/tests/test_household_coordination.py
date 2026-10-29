"""Behavioral tests for evidence-backed orchestration and optional delivery."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.autonomous_lifecycle import (
    AutonomousLifecycle, EvidenceReference, OutcomeVerdict, ReviewedOutcome,
    RoomContinuity, VerifiedAction,
)
from app.services.notification_delivery import send_due_alerts


@pytest.fixture
def coordinator():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    return AutonomousLifecycle(sessions), sessions


def room():
    return RoomContinuity(physical_room_id='room:closet', same_physical_room_verified=True,
                          reason='Two independent models confirm stable physical room features')


def action():
    return VerifiedAction(action_key='sort-scattered-items', title='Sort visible closet items',
        action='Assess and sort items scattered across the closet floor',
        verification_criteria='Floor items are reviewed and no longer obstruct access',
        evidence=EvidenceReference(media_id='original', claim_ids=['e1'],
            original_image_reviewed=True, independent_review_passed=True),
        estimate_min=10, estimate_max=25,
        estimate_rationale='Published task duration from two separate domains',
        estimate_sources=['https://example.org/tips','https://example.com/guide'])


def outcome(task_id, photo, kind, percent=None):
    return ReviewedOutcome(task_id=task_id, verdict=kind,
        evidence=EvidenceReference(media_id=photo, claim_ids=['c1'],
            original_image_reviewed=True, independent_review_passed=True),
        criterion_verified=kind == OutcomeVerdict.completed,
        reviewer_explanation='The newly reviewed image shows the relevant closet floor and visible items',
        progress_percent=percent, next_step='Review items remaining on the closet floor')


def test_household_pulse_is_grounded_and_isolated(coordinator):
    lifecycle, _ = coordinator
    task_id = lifecycle.discover('home', room(), [action()])['created'][0]
    initial = lifecycle.household_pulse('home')
    assert initial['active_count'] == 1
    assert initial['suggestions'][0]['task_id'] == task_id
    assert not initial['suggestions'][0]['research_needed']
    assert lifecycle.household_pulse('other-home')['active_count'] == 0
    lifecycle.verify_fresh_scene('home', room(), [outcome(task_id, 'follow-up', OutcomeVerdict.partially_completed, 40)])
    updated = lifecycle.household_pulse('home')['suggestions'][0]
    assert updated['progress_percent'] == 40
    assert updated['follow_up_reviews'] == 1
    assert 'Review items remaining' in updated['remaining_work']
    lifecycle.verify_fresh_scene('home', room(), [outcome(task_id, 'full', OutcomeVerdict.completed, 100)])
    complete = lifecycle.household_pulse('home')
    assert complete['active_count'] == 0 and complete['verified_complete_count'] == 1


def test_timeline_preserves_every_review_and_blocks_other_households(coordinator):
    lifecycle, _ = coordinator
    tid = lifecycle.discover('home', room(), [action()])['created'][0]
    lifecycle.verify_fresh_scene('home', room(), [outcome(tid, 'unchanged', OutcomeVerdict.still_needed, 0)])
    lifecycle.verify_fresh_scene('home', room(), [outcome(tid, 'partial', OutcomeVerdict.partially_completed, 20)])
    lifecycle.verify_fresh_scene('home', room(), [outcome(tid, 'unreadable', OutcomeVerdict.inconclusive)])
    tl = lifecycle.task_timeline('home', tid)
    assert [e['kind'] for e in tl['events']] == ['discovery', 'verification', 'verification', 'verification']
    assert tl['events'][2]['detail']['progress_percent'] == 20
    assert lifecycle.list_tasks('home')[0]['progress']['percent'] == 20
    with pytest.raises(LookupError):
        lifecycle.task_timeline('other-home', tid)


def test_proactive_daily_reminders_are_time_bound_and_deduplicated(coordinator):
    lifecycle, _ = coordinator
    lifecycle.set_availability('home', timezone_name='America/Phoenix',
        start_time='18:00', end_time='20:00', weekdays=[0, 1, 2, 3, 4])
    lifecycle.discover('home', room(), [action()])
    base = datetime(2026, 10, 26, 18, 10, tzinfo=ZoneInfo('America/Phoenix'))
    assert lifecycle.generate_due_reminders(clock=base) == 1
    assert lifecycle.generate_due_reminders(clock=base) == 0
    assert lifecycle.generate_due_reminders(clock=datetime(2026, 10, 26, 21, 0, tzinfo=ZoneInfo('America/Phoenix'))) == 0
    assert len([a for a in lifecycle.alerts('home') if a['kind'] == 'reminder']) == 1
    assert not lifecycle.alerts('other-home')


def test_email_requires_opt_in_and_is_only_sent_to_named_household(coordinator):
    lifecycle, sessions = coordinator
    lifecycle.discover('home', room(), [action()])
    lifecycle.discover('other-home', room(), [action()])
    config = {'HOMHIVE_EMAIL_ENABLED':'true', 'HOMHIVE_EMAIL_HOUSEHOLD_ID':'home',
        'HOMHIVE_EMAIL_TO':'demo@example.net', 'HOMHIVE_EMAIL_FROM':'assistant@example.net',
        'HOMHIVE_SMTP_USERNAME':'demo-user', 'HOMHIVE_SMTP_PASSWORD':'dummy-test-secret'}
    captured = []
    class FakeSMTP:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def login(self, user, password): assert user == 'demo-user'
        def send_message(self, message): captured.append(message)
    assert send_due_alerts(sessions, config={**config,'HOMHIVE_EMAIL_ENABLED':'false'}, smtp_factory=FakeSMTP) == 0
    assert send_due_alerts(sessions, config=config, smtp_factory=FakeSMTP) == 1
    assert send_due_alerts(sessions, config=config, smtp_factory=FakeSMTP) == 0
    assert len(captured) == 1
    assert captured[0]['To'] == 'demo@example.net'
    assert 'Sort visible closet items' in captured[0].get_content()


def test_incomplete_verdict_cannot_claim_full_criterion_verified():
    with pytest.raises(ValueError, match='uncompleted verdict'):
        ReviewedOutcome(task_id='task', verdict=OutcomeVerdict.partially_completed,
            evidence=EvidenceReference(media_id='photo', claim_ids=['e1'],
                original_image_reviewed=True, independent_review_passed=True),
            criterion_verified=True, reviewer_explanation='A partial view does not establish a fully clear floor',
            progress_percent=30)

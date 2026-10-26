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

def test_first_verified_scan_auto_enrolls_and_completes():
    from types import SimpleNamespace
    e = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(e)
    jobs = AutonomousJobService(sessionmaker(e, expire_on_commit=False))
    jobs.enqueue('h', 'm')
    class Media:
        def get_image(self, household_id, media_id):
            assert (household_id, media_id) == ('h', 'm')
            return SimpleNamespace(content_type='image/jpeg'), b'valid-image'
    calls = []
    def scan(**kwargs):
        calls.append(kwargs)
        return {'status': 'reviewed', 'created': ['task']}
    result = jobs.process_one(media=Media(), bridge=object(), build_pipeline=object(), scan=scan)
    assert result == 'completed'
    assert calls[0]['reference_media_id'] == 'm'
    assert calls[0]['require_room_category'] is True
    assert jobs.jobs('h')[0]['state'] == 'completed'
    assert jobs.rooms('h')[0]['reference_media_id'] == 'm'


def test_first_unverified_scan_never_enrolls_room():
    from types import SimpleNamespace
    e = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(e)
    jobs = AutonomousJobService(sessionmaker(e, expire_on_commit=False))
    jobs.enqueue('h', 'm')
    media = SimpleNamespace(get_image=lambda *_: (SimpleNamespace(content_type='image/jpeg'), b'image'))
    result = jobs.process_one(media=media, bridge=None, build_pipeline=None,
        scan=lambda **_: {'status': 'held_unverified_room'})
    assert result == 'held_unverified_room'
    assert jobs.rooms('h') == []
    assert jobs.jobs('h')[0]['state'] == 'held_unverified_room'


def test_failed_job_can_be_requeued_without_duplication():
    e = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(e)
    jobs = AutonomousJobService(sessionmaker(e, expire_on_commit=False))
    jid = jobs.enqueue('h', 'm')
    jobs.finish(jid, 'failed', 'Review required')
    assert jobs.retry('h', 'm') == jid
    assert jobs.jobs('h')[0]['state'] == 'queued'
    assert len(jobs.jobs('h')) == 1


def test_enrolling_one_held_photo_does_not_requeue_other_household_scans():
    e = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(e)
    jobs = AutonomousJobService(sessionmaker(e, expire_on_commit=False))
    selected = jobs.enqueue('home', 'new-closet')
    other = jobs.enqueue('home', 'other-unverified-photo')
    unrelated = jobs.enqueue('other-home', 'private-photo')
    for jid in (selected, other, unrelated):
        claimed = jobs.claim()
        assert claimed is not None
        jobs.finish(claimed['id'], 'held_unverified_room', 'No unique verified room match')
    # claim order follows enqueue order on an in-memory DB.
    room_id = jobs.enroll('home', 'new-closet')
    assert room_id == 'reference:new-closet'
    by_home = {row['media_id']: row for row in jobs.jobs('home')}
    assert by_home['new-closet']['state'] == 'queued'
    assert by_home['new-closet']['attempts'] == 0
    assert by_home['new-closet']['room_id'] == room_id
    assert by_home['other-unverified-photo']['state'] == 'held_unverified_room'
    assert jobs.jobs('other-home')[0]['state'] == 'held_unverified_room'
    assert jobs.enroll('home', 'new-closet') == room_id
    assert len(jobs.rooms('home')) == 1
    assert {row['media_id']: row for row in jobs.jobs('home')}['other-unverified-photo']['state'] == 'held_unverified_room'


def test_explicitly_enrolled_reference_is_not_blocked_by_similarity_to_another_room():
    from types import SimpleNamespace
    from unittest.mock import patch
    e = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(e)
    jobs = AutonomousJobService(sessionmaker(e, expire_on_commit=False))
    jobs.enroll('home', 'old-reference')
    jid = jobs.enqueue('home', 'new-closet')
    jobs.finish(jid, 'held_unverified_room', 'No unique verified room match')
    jobs.enroll('home', 'new-closet')

    class Media:
        def get_image(self, household_id, media_id):
            assert household_id == 'home'
            return SimpleNamespace(content_type='image/jpeg'), media_id.encode()

    requests = []
    def scan(**kwargs):
        requests.append(kwargs)
        return {'status': 'reviewed', 'created': [], 'existing': [],
                'room_category': 'walk-in closet', 'review_summary': {}}
    def no_pair_comparisons(*args, **kwargs):
        raise AssertionError('User-enrolled reference must not be overridden by inferred similarity')

    with patch('app.vision.autonomous_api.verify_room_pair', side_effect=no_pair_comparisons):
        state = jobs.process_one(media=Media(), bridge=object(), build_pipeline=lambda: None, scan=scan)
    assert state == 'completed'
    assert requests[0]['media_id'] == 'new-closet'
    assert requests[0]['reference_media_id'] == 'new-closet'
    assert jobs.jobs('home')[0]['room_id'] == 'reference:new-closet'


def test_scan_failure_messages_are_specific_but_do_not_leak_provider_content():
    from app.services.autonomous_jobs import _user_failure_message

    class ProviderError(Exception):
        def __init__(self, code):
            super().__init__('Sensitive provider text with secret=hidden')
            self.response = type('Response', (), {'status_code': code})()

    assert 'credentials' in _user_failure_message(ProviderError(401), retrying=False)
    assert 'usage limit' in _user_failure_message(ProviderError(429), retrying=True)
    assert 'incomplete or invalid' in _user_failure_message(
        ValueError('Planner response missing required actions field'), retrying=False)
    for exc in (ProviderError(401), ProviderError(429), ValueError('untrusted provider body')):
        assert 'secret' not in _user_failure_message(exc, retrying=False)
        assert 'Sensitive' not in _user_failure_message(exc, retrying=True)


def test_failed_scan_stores_actionable_non_sensitive_cause():
    e = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(e)
    jobs = AutonomousJobService(sessionmaker(e, expire_on_commit=False))
    jobs.enqueue('home', 'missing-image')
    from types import SimpleNamespace
    # A missing photograph has its own explicit and accurate failure message.
    assert jobs.process_one(media=SimpleNamespace(get_image=lambda *_: None),
        bridge=None, build_pipeline=None, scan=None) == 'failed'
    result = jobs.jobs('home')[0]
    assert result['state'] == 'failed'
    assert 'Image no longer available' in result['message']

"""Server-owned demo scene identity. No claims inferred from user-provided filenames."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService
from app.services.demo_scene_identity import verified_demo_scene


ASSET_DIR = Path(__file__).resolve().parents[2] / 'frontend' / 'public' / 'demo-library'

# Use manifest fingerprints with a fixed fake to avoid requiring the assets.


def service():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    return AutonomousJobService(sessionmaker(engine, expire_on_commit=False))


class Media:
    def __init__(self, payloads): self.payloads = payloads
    def get_image(self, household_id, media_id):
        if media_id not in self.payloads: return None
        return SimpleNamespace(content_type='image/jpeg'), self.payloads[media_id]


def sample_scan(**kwargs):
    return {'status': 'reviewed', 'room_category': 'Kitchen', 'created': [], 'existing': [],
            'review_summary': {'room_category':'Kitchen', 'room_identity_source':'model_verified'}}


def test_known_demo_pair_matches_existing_without_paid_identity_calls():
    jobs = service()
    jobs.enroll('home', 'original', 'Kitchen')
    jobs.enqueue('home', 'variant')
    media = Media({'original':b'first', 'variant':b'second'})
    trusted = {'first':{'family':'original-30','category':'Kitchen'},
               'second':{'family':'original-30','category':'Kitchen'}}
    captured = []
    with patch('app.services.autonomous_jobs.verified_demo_scene', side_effect=lambda b:trusted.get(b.decode())), \
         patch('app.vision.autonomous_api.verify_room_pair',side_effect=AssertionError('Do not call paid room match')):
        result = jobs.process_one(media=media, bridge=None, build_pipeline=lambda: None,
                                  scan=lambda **kw: captured.append(kw) or sample_scan(**kw))
    assert result == 'completed'
    assert len(jobs.rooms('home')) == 1
    assert captured[0]['trusted_demo_relationship'] is True
    assert jobs.jobs('home')[0]['room_id'] == 'reference:original'


def test_independent_demo_scene_auto_enrolls_new_uniquely_named_kitchen():
    jobs = service()
    jobs.enroll('home','old','Kitchen')
    jobs.enqueue('home','new')
    media = Media({'old':b'old-family','new':b'new-family'})
    trusted={'old-family':{'family':'original-18','category':'Kitchen'},
             'new-family':{'family':'original-30','category':'Kitchen'}}
    with patch('app.services.autonomous_jobs.verified_demo_scene', side_effect=lambda b:trusted.get(b.decode())), \
         patch('app.vision.autonomous_api.verify_room_pair',side_effect=AssertionError('Demo family fast path')):
        assert jobs.process_one(media=media, bridge=None, build_pipeline=lambda: None, scan=sample_scan) == 'completed'
    assert {r['room_category'] for r in jobs.rooms('home')} == {'Kitchen','Kitchen 2'}
    assert jobs.jobs('home')[0]['review_summary']['room_identity_source'] == 'verified_demo_new_scene'
    jobs.set_room_category('home','reference:new','Kitchen')
    assert {r['room_category'] for r in jobs.rooms('home')} == {'Kitchen','Kitchen 2'}


def test_unknown_user_photo_is_never_classified_as_new_by_demo_metadata():
    jobs=service()
    jobs.enroll('home','old','Kitchen')
    jobs.enqueue('home','user-photo')
    media=Media({'old':b'old-family','user-photo':b'unknown'})
    known={'old-family':{'family':'original-18','category':'Kitchen'}}
    with patch('app.services.autonomous_jobs.verified_demo_scene',side_effect=lambda b:known.get(b.decode())), \
         patch('app.vision.autonomous_api.verify_room_pair',return_value=False):
        assert jobs.process_one(media=media, bridge=None,
               build_pipeline=lambda:(SimpleNamespace(independent=None),None,None), scan=sample_scan) == 'held_unverified_room'
    assert len(jobs.rooms('home')) == 1


def test_same_family_shared_by_two_rooms_is_not_automatically_merged():
    jobs=service()
    jobs.enroll('home','a','Kitchen')
    jobs.enroll('home','b','Kitchen')
    jobs.enqueue('home','new')
    media=Media({'a':b'a','b':b'b','new':b'new'})
    trusted={key:{'family':'original-30','category':'Kitchen'} for key in ['a','b','new']}
    with patch('app.services.autonomous_jobs.verified_demo_scene', side_effect=lambda b:trusted.get(b.decode())):
        assert jobs.process_one(media=media, bridge=None, build_pipeline=lambda:None, scan=sample_scan)=='held_unverified_room'
    assert len(jobs.rooms('home'))==2


def test_category_names_remain_distinct_in_same_household_only():
    jobs=service()
    assert jobs.enroll('home','a','Kitchen')=='reference:a'
    assert jobs.enroll('home','b','Kitchen')=='reference:b'
    assert jobs.enroll('home','c','Kitchen')=='reference:c'
    assert [r['room_category'] for r in jobs.rooms('home')] == ['Kitchen','Kitchen 2','Kitchen 3']
    assert jobs.enroll('other','d','Kitchen')=='reference:d'
    assert jobs.rooms('other')[0]['room_category']=='Kitchen'


def test_unknown_and_ambiguous_sources_have_no_verified_family():
    assert verified_demo_scene(b'not-a-verified-demo-photo') is None

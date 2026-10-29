"""Object scope is durable, household isolated and independent from room identity."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.services.autonomous_objects import ObjectRegistry, AutonomousObjectRecord
from app.services.autonomous_lifecycle import (
    AutonomousLifecycle, RoomContinuity, VerifiedAction, EvidenceReference,
    ReviewedOutcome, OutcomeVerdict,
)
from app.services.autonomous_jobs import AutonomousJobService


@pytest.fixture
def app_state():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    yield ObjectRegistry(sessions), AutonomousLifecycle(sessions), AutonomousJobService(sessions)
    engine.dispose()


def reviewed_action(media='photo-one'):
    return VerifiedAction(action_key='plant-moisture-check', title='Check plant soil',
        action='Inspect soil moisture and plant care history',
        verification_criteria='Soil condition has been physically inspected',
        evidence=EvidenceReference(media_id=media, claim_ids=['c1'],
            independent_review_passed=True, original_image_reviewed=True))


def test_creates_unique_named_object_without_room(app_state):
    registry, _, _ = app_state
    first = registry.resolve('home', 'photo1', 'plant', evidence=['Yellowing leaves visible'])
    second = registry.resolve('home', 'photo2', 'plant', evidence=['Plant wilting'])
    rows = registry.list('home')
    assert [r['name'] for r in rows] == ['Household Plant 1', 'Household Plant 2']
    assert first != second
    assert registry.list('other') == []


def test_same_object_across_exact_media_and_verified_family(app_state):
    registry, _, _ = app_state
    a = registry.resolve('home', 'original', 'plant', demo_family='original-145',
        image_hash='abc', evidence=['Leaves are yellow'])
    assert registry.resolve('home', 'variant', 'plant', demo_family='original-145',
        image_hash='def', evidence=['Leaves remain yellow']) == a
    assert registry.resolve('home', 'new-upload', 'plant', image_hash='abc') == a
    assert registry.lookup('home','new-upload') == a
    assert registry.resolve('other', 'original', 'plant',demo_family='original-145') != a


def test_location_change_preserves_identity_and_tasks(app_state):
    registry, lifecycle, jobs = app_state
    obj = registry.resolve('home','photo1','plant')
    continuity=RoomContinuity(physical_object_id=obj,same_physical_object_verified=True,
        reason='Independently reviewed plant close-up')
    created=lifecycle.discover('home',continuity,[reviewed_action()])['created'][0]
    assert lifecycle.list_tasks('home')[0]['object_id'] == obj
    assert lifecycle.list_tasks('home')[0]['room_id'] == f'object:{obj}'
    room_id=jobs.enroll('home','bedroom-photo','Bedroom')
    registry.set_room('home',obj,room_id)
    assert registry.list('home')[0]['name'] == 'Bedroom Plant 1'
    assert registry.list('home')[0]['id'] == obj
    assert lifecycle.list_tasks('home')[0]['id'] == created


def test_repeats_do_not_duplicate_object_tasks(app_state):
    registry, lifecycle, _ = app_state
    obj=registry.resolve('home','photo1','plant')
    scope=RoomContinuity(physical_object_id=obj,same_physical_object_verified=True,
        reason='Same independently reviewed plant')
    a=lifecycle.discover('home',scope,[reviewed_action('photo1')])
    b=lifecycle.discover('home',scope,[reviewed_action('photo2')])
    assert b['existing'] == a['created']
    assert len(lifecycle.list_tasks('home')) == 1


def test_object_task_cannot_be_closed_by_unrelated_room_or_object(app_state):
    registry, lifecycle, _=app_state
    obj=registry.resolve('home','photo1','plant')
    other=registry.resolve('home','photo2','plant')
    scope=RoomContinuity(physical_object_id=obj,same_physical_object_verified=True,
        reason='Same independently reviewed plant')
    task=lifecycle.discover('home',scope,[reviewed_action()])['created'][0]
    verdict=ReviewedOutcome(task_id=task,verdict=OutcomeVerdict.completed,
        criterion_verified=True,reviewer_explanation='The soil test was independently witnessed',
        evidence=EvidenceReference(media_id='fresh-photo', claim_ids=['c1'],
            original_image_reviewed=True, independent_review_passed=True))
    wrong=RoomContinuity(physical_object_id=other,same_physical_object_verified=True,
        reason='Different independently reviewed plant')
    assert lifecycle.verify_fresh_scene('home',wrong,[verdict])[task] == 'unmatched_task_or_room'
    wrong_room=RoomContinuity(physical_room_id='bedroom',same_physical_room_verified=True,
        reason='Room view cannot verify this plant')
    assert lifecycle.verify_fresh_scene('home',wrong_room,[verdict])[task] == 'unmatched_task_or_room'


def test_household_scoping_prevents_cross_household_location_edit(app_state):
    registry, _, jobs=app_state
    obj=registry.resolve('home','photo1','object')
    room=jobs.enroll('home','room-photo','Bedroom')
    with pytest.raises(LookupError): registry.set_room('other', obj, room)
    with pytest.raises(LookupError): registry.set_room('home',obj,'nonexistent')


def test_independently_reviewed_closeup_uses_object_not_fake_room(app_state, monkeypatch):
    from types import SimpleNamespace
    from app.services.autonomous_scan_bridge import AutonomousScanBridge
    from app.services.open_world_planning import Evidence
    from app.vision.autonomous_api import run_autonomous_scan
    registry, lifecycle, _ = app_state
    media = SimpleNamespace(get_image=lambda home, photo: (
        SimpleNamespace(content_type='image/jpeg'), b'plant-photo'))
    evidence = Evidence(id='e1',description='A potted plant with yellowing leaves is clearly visible',
        provenance='visible',source_id='plant-photo-id')
    preview = SimpleNamespace(corroborated_evidence=[evidence], room_category=None,
        approved_actions=[], rejected_actions=[], proposal_reviews=[], proposed_count=0,
        verification='corroborated',model_audit={'primary_claims':['e1']})
    monkeypatch.setattr('app.vision.autonomous_api.preview_verified_scene',lambda **kw: preview)
    result = run_autonomous_scan(household_id='home',media_id='plant-photo-id',
        reference_media_id='plant-photo-id',media=media,
        bridge=AutonomousScanBridge(lifecycle),build_pipeline=lambda: (
            SimpleNamespace(independent=None),None,None),object_probe=True,object_registry=registry)
    assert result['status'] == 'reviewed'
    assert result['room_id'] is None
    assert result['object_id'] == registry.list('home')[0]['id']
    assert registry.list('home')[0]['name'] == 'Household Plant 1'
    assert result['review_summary']['scene_focus']['focus'] == 'object'


def test_object_card_sources_use_verified_scan_research_not_room_or_task(app_state):
    from datetime import datetime, timezone
    from app.services.autonomous_jobs import AutonomousScanJob
    registry, _, _ = app_state
    obj_id = registry.resolve('home', 'plant-photo', 'plant', demo_family='original-145',
        evidence=['Many leaves of this houseplant are brown and shriveled.'])
    now = datetime.now(timezone.utc)
    with registry.sessions.begin() as db:
        db.add(AutonomousScanJob(id='plant-scan', household_id='home', media_id='plant-photo',
            room_id=None, state='completed', attempts=1, next_attempt_at=now,
            updated_at=now, message='', review_summary={'object_id':obj_id,
                'automatic_coordination': {'status':'completed','scene_research':[{
                    'topic':'plant_care','sources':[{'title':'Plant care basics',
                        'url':'https://university.example.edu/guidance',
                        'excerpt':'Brown leaves can have several causes; inspect soil moisture.'}]}]}}))
    result = registry.list('home')[0]
    assert result['name'] == 'Household Plant 1'
    assert result['catalog_candidate'] is None
    assert result['catalog_reference'] is None
    assert result['identity_status'] == 'unknown'
    assert result['research_sources'][0]['url'] == 'https://university.example.edu/guidance'
    assert registry.list('other') == []

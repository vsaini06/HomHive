import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.services.autonomous_lifecycle import (
    AutonomousLifecycle, EvidenceReference, RoomContinuity, ReviewedOutcome, OutcomeVerdict,
)
from app.services.autonomous_scan_bridge import (
    AutonomousScanBridge, VerifiedScan, ScanOutcomeReview,
)
from app.services.open_world_planning import ActionProposal, Evidence


@pytest.fixture
def bridge():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    return AutonomousScanBridge(AutonomousLifecycle(sessionmaker(bind=engine, expire_on_commit=False)))


def room(name='stable-room-A', verified=True):
    return RoomContinuity(physical_room_id=name, same_physical_room_verified=verified,
                          reason='Verified stable location using separate room evidence')


def evidence(photo='first', eid='e1'):
    return Evidence(id=eid, description='Clothes scattered across the floor',
                    provenance='visible', source_id=photo)


def action():
    return ActionProposal(action_id='a1', title='Clear the floor',
                          action='Gather the scattered items from the visible floor',
                          supporting_evidence_ids=['e1'],
                          verification_criteria='The floor no longer contains scattered clothing')


def scan(photo='first', matching_room=None):
    return VerifiedScan(media_id=photo, corroborated_evidence=[evidence(photo)],
                        approved_actions=[action()], independently_reviewed=True,
                        original_media_reviewed=True, room=matching_room or room())


def outcome(task_id, photo='second'):
    return ReviewedOutcome(task_id=task_id, verdict=OutcomeVerdict.completed,
        evidence=EvidenceReference(media_id=photo, claim_ids=['e2'], original_image_reviewed=True,
                                   independent_review_passed=True), criterion_verified=True,
        reviewer_explanation='The targeted floor area is visibly free of scattered items')


def review(task_id, photo='second', match=None):
    obs = Evidence(id='e2', description='Target floor is now free of scattered clothing',
                   provenance='visible', source_id=photo)
    return ScanOutcomeReview(media_id=photo, room=match or room(),
                             corroborated_evidence=[obs], outcomes=[outcome(task_id, photo)])


def test_verified_scan_creates_pending_task_without_effort(bridge):
    result = bridge.persist_verified_scan('home1', scan())
    assert len(result['created']) == 1
    assert bridge.get_tasks('home1')[0]['effort_min'] is None


def test_repeat_scan_deduplicates(bridge):
    task_id = bridge.persist_verified_scan('home1', scan())['created'][0]
    assert bridge.persist_verified_scan('home1', scan('second'))['existing'] == [task_id]


def test_unverified_room_holds_creation(bridge):
    assert bridge.persist_verified_scan('home1', scan(matching_room=room(verified=False)))['held_for_room_identity'] == 1
    assert bridge.get_tasks('home1') == []


def test_fresh_verified_completion(bridge):
    task_id = bridge.persist_verified_scan('home1', scan())['created'][0]
    assert bridge.reconcile_verified_scan('home1', review(task_id))[task_id] == 'completed'
    assert bridge.get_tasks('home1')[0]['status'] == 'completed'


def test_wrong_room_cannot_complete(bridge):
    task_id = bridge.persist_verified_scan('home1', scan())['created'][0]
    assert bridge.reconcile_verified_scan('home1', review(task_id, match=room('other-room')))[task_id] == 'unmatched_task_or_room'


def test_missing_provenance_rejected(bridge):
    s = scan().model_dump(mode='json')
    s['corroborated_evidence'][0]['source_id'] = 'another-image'
    with pytest.raises(ValueError, match='refer to this scan'):
        VerifiedScan.model_validate(s)


def test_unreviewed_scan_rejected():
    s = scan().model_dump(mode='json')
    s['independently_reviewed'] = False
    with pytest.raises(ValueError, match='Independent'):
        VerifiedScan.model_validate(s)


def test_cross_image_outcome_rejected(bridge):
    task_id = bridge.persist_verified_scan('home1', scan())['created'][0]
    bad = review(task_id).model_dump(mode='json')
    bad['outcomes'][0]['evidence']['media_id'] = 'unrelated'
    with pytest.raises(ValueError, match='different photograph'):
        ScanOutcomeReview.model_validate(bad)


def test_outcome_evidence_must_be_corroborated(bridge):
    task_id = bridge.persist_verified_scan('home1', scan())['created'][0]
    bad = review(task_id).model_dump(mode='json')
    bad['outcomes'][0]['evidence']['claim_ids'] = ['nonexistent']
    with pytest.raises(ValueError, match='corroborated'):
        ScanOutcomeReview.model_validate(bad)


def test_original_photo_cannot_complete(bridge):
    task_id = bridge.persist_verified_scan('home1', scan())['created'][0]
    original = review(task_id, photo='first')
    assert bridge.reconcile_verified_scan('home1', original)[task_id] == 'requires_fresh_media'


def test_household_isolation(bridge):
    bridge.persist_verified_scan('home1', scan())
    assert bridge.get_tasks('other-household') == []

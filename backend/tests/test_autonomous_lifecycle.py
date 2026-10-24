import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.services.autonomous_lifecycle import (
    AutonomousLifecycle, AutonomousTaskEventRecord, EvidenceReference,
    RoomContinuity, ReviewedOutcome, OutcomeVerdict, VerifiedAction,
)

@pytest.fixture
def lifecycle():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    return AutonomousLifecycle(sessionmaker(bind=engine, expire_on_commit=False)), engine

def room(id='utility-1', verified=True):
    return RoomContinuity(physical_room_id=id, same_physical_room_verified=verified,reason='Separate matching evidence corroborates room')

def action(media='photo1', key='tidy-clothing-001'):
    return VerifiedAction(action_key=key,title='Organize garments',action='Gather and store clothes from floor',verification_criteria='Floor space is clear of scattered clothing',evidence=EvidenceReference(media_id=media,claim_ids=['e1'],original_image_reviewed=True,independent_review_passed=True))

def outcome(task_id, media='photo2', verdict=OutcomeVerdict.completed, criterion=True):
    return ReviewedOutcome(task_id=task_id,verdict=verdict,evidence=EvidenceReference(media_id=media,claim_ids=['fresh1'],original_image_reviewed=True,independent_review_passed=True),criterion_verified=criterion,reviewer_explanation='The previously cluttered floor is visibly clear')

def test_creates_task_with_unknown_duration(lifecycle):
    service,_=lifecycle
    result=service.discover('h1',room(),[action()])
    assert len(result['created'])==1
    tasks=service.list_tasks('h1')
    assert tasks[0]['effort_min'] is None and tasks[0]['status']=='pending'

def test_no_room_identity_no_task(lifecycle):
    service,_=lifecycle
    result=service.discover('h1',room(verified=False),[action()])
    assert result['held_for_room_identity']==1 and service.list_tasks('h1')==[]

def test_idempotent_across_multiple_images(lifecycle):
    service,engine=lifecycle
    result=service.discover('h1',room(),[action()]); first=result['created'][0]
    second=service.discover('h1',room(),[action('photo2')]); third=service.discover('h1',room(),[action('photo2')])
    assert second['existing']==[first] and third['existing']==[first]
    with sessionmaker(bind=engine)() as db:
        assert db.scalar(select(func.count()).select_from(AutonomousTaskEventRecord))==2

def test_independent_households_and_rooms(lifecycle):
    service,_=lifecycle
    for household, r in [('h1','utility1'),('h2','utility1'),('h1','utility2')]:
        service.discover(household,room(r),[action()])
    assert len(service.list_tasks('h1'))==2 and len(service.list_tasks('h2'))==1

def test_same_room_fresh_verified_completion(lifecycle):
    service,_=lifecycle
    task_id=service.discover('h1',room(),[action()])['created'][0]
    result=service.verify_fresh_scene('h1',room(),[outcome(task_id)])
    assert result[task_id]=='completed'
    assert service.list_tasks('h1')[0]['status']=='completed'

def test_wrong_room_cannot_close(lifecycle):
    service,_=lifecycle
    task_id=service.discover('h1',room(),[action()])['created'][0]
    assert service.verify_fresh_scene('h1',room('other-room'),[outcome(task_id)])[task_id]=='unmatched_task_or_room'
    assert service.list_tasks('h1')[0]['status']=='pending'

def test_unverified_room_cannot_close(lifecycle):
    service,_=lifecycle
    task_id=service.discover('h1',room(),[action()])['created'][0]
    assert service.verify_fresh_scene('h1',room(verified=False),[outcome(task_id)])[task_id]=='held_unverified_room'

def test_original_photo_cannot_verify_own_completion(lifecycle):
    service,_=lifecycle
    task_id=service.discover('h1',room(),[action()])['created'][0]
    assert service.verify_fresh_scene('h1',room(),[outcome(task_id,'photo1')])[task_id]=='requires_fresh_media'

def test_inconclusive_doesnt_close(lifecycle):
    service,_=lifecycle
    task_id=service.discover('h1',room(),[action()])['created'][0]
    res=service.verify_fresh_scene('h1',room(),[outcome(task_id,verdict=OutcomeVerdict.inconclusive,criterion=False)])
    assert res[task_id]=='kept_active'

def test_no_completion_without_verified_criterion():
    with pytest.raises(ValueError,match='criterion'):
        outcome('t1',criterion=False)

def test_no_proposal_without_independent_review():
    with pytest.raises(ValueError,match='independent'):
        VerifiedAction(action_key='task-key-123',title='Organize floor',action='Clear visible clutter', verification_criteria='Floor is clear in a new image',evidence=EvidenceReference(media_id='p',claim_ids=['e'],original_image_reviewed=True,independent_review_passed=False))

def test_completed_does_not_reset_on_repeat(lifecycle):
    service,_=lifecycle
    task_id=service.discover('h1',room(),[action()])['created'][0]
    service.verify_fresh_scene('h1',room(),[outcome(task_id)])
    service.discover('h1',room(),[action('photo3')])
    assert service.list_tasks('h1')[0]['status']=='completed'

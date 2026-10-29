"""Offline coverage for bounded post-scan work; fake providers never spend credits."""
from datetime import datetime, timezone
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.coordination.auto_orchestration import HouseholdAutoOrchestrator, research_topic
from app.research.models import ResearchPurpose
from app.services.autonomous_jobs import AutonomousScanJob
from app.services.autonomous_lifecycle import AutonomousTaskRecord, AutonomousLifecycle, RoomContinuity
from app.services.autonomous_scan_bridge import VerifiedScan, to_verified_action
from app.services.open_world_planning import ActionProposal, EffortEstimate, Evidence


def setup_case(*, task_title='Inspect yellowing leaves on a houseplant',
               task_action='Check the plant for yellowing leaves and possible issues',
               with_task=True):
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with sessions.begin() as db:
        db.add(AutonomousScanJob(id='scan1', household_id='home', media_id='photo1', room_id='room1',
            state='completed', attempts=1, next_attempt_at=now, updated_at=now, message='',
            review_summary={'created_count': int(with_task), 'progress_results': {}}))
        if with_task:
            db.add(AutonomousTaskRecord(household_id='home', id='task1', physical_room_id='room1',
                action_key='plant_task_key', title=task_title, action=task_action,
                criteria='The visible issue has been evaluated', state='pending',
                effort_min=None, effort_max=None, task_payload={
                    'evidence': {'media_id':'photo1', 'claim_ids':['e1']},
                    'evidence_summary':'Yellowing leaves are visible.', 'estimate_sources': []},
                created_at=now, updated_at=now))
    return sessions, engine


class FakeProvider:
    def __init__(self):
        self.requests = []
    def search(self, request):
        self.requests.append(request)
        if request.purpose == ResearchPurpose.PLANT_CARE:
            return SimpleNamespace(evidence=[SimpleNamespace(
                title='Plant care guidance', url='https://plants.example.org/plant-care',
                content='Yellowing leaves have several causes.')])
        return SimpleNamespace(evidence=[
            SimpleNamespace(title='Task time', url='https://one.example.org/time',
                            content='Allow 15 minutes to inspect plant leaves.'),
            SimpleNamespace(title='Task time', url='https://two.example.net/time',
                            content='Inspecting plant leaves usually takes 20 minutes.'),
        ])


def fake_advice(plan):
    return {'source':'nebius_token_factory_nvidia_nemotron',
            'model':'nvidia/nemotron-3-super-120b-a12b', 'selected_task_id':None,
            'summary':'No work is currently executable.',
            'reason':'The explicit presence, availability and preference requirements were not met.'}


def test_plant_scan_researches_then_replans_once():
    sessions, engine = setup_case()
    provider = FakeProvider()
    calls = []
    def advice(plan):
        calls.append(plan)
        return fake_advice(plan)
    orch = HouseholdAutoOrchestrator(sessions, provider=provider, advice=advice)
    result = orch.after_scan('scan1')
    assert result['status'] == 'completed'
    assert result['researched_tasks'] == 1
    assert result['source_count'] >= 1
    assert result['planning_status'] == 'advised'
    assert [req.purpose for req in provider.requests] == [ResearchPurpose.HOUSEHOLD_CONTEXT, ResearchPurpose.PLANT_CARE]
    assert len(calls) == 1
    with sessions() as db:
        task = db.get(AutonomousTaskRecord, ('home', 'task1'))
        assert len(task.task_payload['estimate_sources']) == 2
        assert task.effort_max == 20
        assert task.task_payload['automatic_guidance']['sources'][0]['url'].startswith('https://')
        assert db.get(AutonomousScanJob, 'scan1').review_summary['automatic_coordination']['status'] == 'completed'
    assert orch.after_scan('scan1') is None
    assert len(provider.requests) == 2
    assert len(calls) == 1
    engine.dispose()


def test_unchanged_scan_does_not_call_external_providers():
    sessions, engine = setup_case(with_task=False)
    provider = FakeProvider()
    orch = HouseholdAutoOrchestrator(sessions, provider=provider,
                                      advice=lambda plan: (_ for _ in ()).throw(AssertionError('not needed')))
    assert orch.after_scan('scan1')['planning_status'] == 'unchanged_scene'
    assert provider.requests == []
    engine.dispose()


def test_ordinary_dishes_do_not_trigger_plant_or_appliance_research():
    sessions, engine = setup_case(task_title='Wash the dishes in the sink',
        task_action='Wash the dishes using dish soap')
    with sessions.begin() as db:
        record = db.get(AutonomousTaskRecord, ('home', 'task1'))
        payload = dict(record.task_payload)
        payload['evidence_summary'] = 'Dirty dishes visible in sink.'
        record.task_payload = payload
    provider = FakeProvider()
    orch = HouseholdAutoOrchestrator(sessions, provider=provider, advice=fake_advice)
    result = orch.after_scan('scan1')
    assert result['researched_tasks'] == 0
    assert len(provider.requests) == 1
    assert provider.requests[0].purpose == ResearchPurpose.HOUSEHOLD_CONTEXT
    engine.dispose()


def test_hazardous_plant_scenario_does_not_auto_research():
    item = SimpleNamespace(title='Check plant near a live wire', action='Danger of electrical shock',
                           task_payload={'evidence_summary':'Yellowing plant leaves'})
    assert research_topic(item) is None


def test_verified_effort_urls_survive_conversion_to_persistent_action():
    evidence = Evidence(id='e1', description='Leaves have visible yellow patches',
                        provenance='visible', source_id='photo1')
    action = ActionProposal(action_id='a1', title='Inspect yellowing plant leaves',
        action='Inspect the plant leaves without assuming a diagnosis',
        supporting_evidence_ids=['e1'],
        verification_criteria='The plant leaves have been inspected for visible issues',
        estimated_effort=EffortEstimate(minimum_minutes=10, maximum_minutes=15,
            rationale='External duration research from two distinct domains',
            evidence_ids=['e1'], externally_verified=True,
            source_urls=['https://one.example.org/time', 'https://two.example.net/time']))
    scan = VerifiedScan(media_id='photo1', corroborated_evidence=[evidence],
        approved_actions=[action], independently_reviewed=True, original_media_reviewed=True,
        room=RoomContinuity(physical_room_id='room1', same_physical_room_verified=True,
            reason='Trusted original image'), room_category='living room')
    persisted = to_verified_action(action, scan)
    assert persisted.estimate_sources == ['https://one.example.org/time', 'https://two.example.net/time']


def test_context_tick_only_reacts_to_material_change_without_spending_on_ineligible_tasks():
    from app.coordination.service import set_availability
    sessions, engine = setup_case()
    provider = FakeProvider()
    calls = []
    def advisor(plan):
        calls.append(plan)
        return fake_advice(plan)
    orch = HouseholdAutoOrchestrator(sessions, provider=provider, advice=advisor)
    assert orch.after_scan('scan1')['status'] == 'completed'
    assert len(calls) == 1
    assert orch.on_context_tick() == 0
    set_availability(sessions, 'home', 'BUSY')
    assert orch.on_context_tick() == 1

    assert len(calls) == 1
    assert orch.on_context_tick() == 0
    engine.dispose()


def test_scene_research_uses_reviewed_plant_evidence_even_without_a_task():
    from app.coordination.auto_orchestration import scene_research_topics
    topics = scene_research_topics({'evidence': [
        'A potted variegated pothos has yellowing and drooping leaves.'
    ]})
    assert len(topics) == 1
    assert topics[0][0] == ResearchPurpose.PLANT_CARE
    sessions, engine = setup_case(with_task=False)
    with sessions.begin() as db:
        job = db.get(AutonomousScanJob, 'scan1')
        job.review_summary = {'evidence': [
            'A potted variegated pothos has yellowing and drooping leaves.'
        ]}
    provider = FakeProvider()
    orch = HouseholdAutoOrchestrator(sessions, provider=provider, advice=fake_advice)
    result = orch.after_scan('scan1')
    assert result['status'] == 'completed'
    assert result['scene_research'][0]['topic'] == 'plant_care'
    assert result['scene_research'][0]['sources'][0]['url'].startswith('https://')
    assert provider.requests[0].purpose == ResearchPurpose.PLANT_CARE
    assert orch.after_scan('scan1') is None
    assert len(provider.requests) == 1
    engine.dispose()


def test_new_appliance_without_fault_triggers_safe_guidance():
    from app.coordination.auto_orchestration import scene_research_topics
    topics = scene_research_topics({'evidence': ['A microwave oven is visible near the counter.']})
    assert len(topics) == 1
    assert topics[0][0] == ResearchPurpose.APPLIANCE_GUIDANCE
    assert 'verify the exact model' in topics[0][1]
    assert scene_research_topics({'evidence': ['A bowl of dishes is visible.']}) == []
    assert scene_research_topics({'evidence': ['A gas leak may be present near the stove.']}) == []


def test_room_mismatch_still_researches_task_from_exact_verified_image():
    sessions, engine = setup_case()
    with sessions.begin() as db:
        task = db.get(AutonomousTaskRecord, ('home','task1'))
        task.physical_room_id = 'reference:other_room'
    provider = FakeProvider()
    orch = HouseholdAutoOrchestrator(sessions, provider=provider, advice=fake_advice)
    result = orch.after_scan('scan1')
    assert result['researched_tasks'] == 1
    with sessions() as db:
        task = db.get(AutonomousTaskRecord, ('home','task1'))
        assert task.task_payload['automatic_guidance']['sources']
    engine.dispose()


def test_missed_scan_can_recover_once_without_duplicate_calls():
    sessions, engine = setup_case()
    provider = FakeProvider()
    calls = []
    def advice(plan):
        calls.append(plan)
        return fake_advice(plan)
    orch = HouseholdAutoOrchestrator(sessions, provider=provider, advice=advice)
    assert orch.recover_recent_scans(max_scans=2) == 1
    assert orch.recover_recent_scans(max_scans=2) == 0
    assert len(calls) == 1
    engine.dispose()


def test_object_only_scan_researches_without_room_assignment():
    from app.services.autonomous_objects import ObjectRegistry
    sessions, engine = setup_case(with_task=False)
    obj = ObjectRegistry(sessions).resolve('home','photo1','plant',
        evidence=['Yellowing leaves on a potted plant are visible'])
    with sessions.begin() as db:
        job = db.get(AutonomousScanJob,'scan1')
        job.room_id = None
        job.review_summary = {'object_id': obj, 'evidence':[
            'A potted houseplant has yellowing, brown leaves'], 'created_count':0}
    provider = FakeProvider()
    orch = HouseholdAutoOrchestrator(sessions, provider=provider, advice=fake_advice)
    result = orch.after_scan('scan1')
    assert result['status'] == 'completed'
    assert result['research_status'] == 'sources_found'
    assert result['scene_research'][0]['topic'] == 'plant_care'
    assert result['source_count'] == 1
    assert len(provider.requests) == 1
    assert orch.after_scan('scan1') is None
    engine.dispose()

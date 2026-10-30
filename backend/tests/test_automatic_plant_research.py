"""Plant references from corroborated photos, without inventing species or chores."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.coordination.auto_orchestration import (
    HouseholdAutoOrchestrator, external_reference_for_scene,
    reason_scene_research_topics, scene_research_topics,
)
from app.db.base import Base
from app.research.models import ResearchPurpose
from app.services.autonomous_jobs import AutonomousScanJob


class ResearchPlanner:
    def __init__(self, topics):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.topics = topics
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason='stop', message=SimpleNamespace(
                content=json.dumps({'topics': self.topics})))])


class TavilyStub:
    def __init__(self):
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        return SimpleNamespace(evidence=[SimpleNamespace(
            title='Horticultural care guide',
            url='https://example.org/plant-care',
            content='Check leaf characteristics and soil moisture before choosing watering needs.')])


def test_balcony_plant_gets_a_care_lookup_without_visual_symptoms():
    topics = scene_research_topics({'evidence': [
        'A potted green plant with long narrow leaves is on the balcony.',
    ]})
    assert len(topics) == 1
    assert topics[0][0] is ResearchPurpose.PLANT_CARE
    assert 'visible leaf shape' in topics[0][1]
    assert 'not assert a species' in topics[0][1]


def test_nemotron_can_request_photo_grounded_plant_care_search():
    model = ResearchPlanner([{
        'purpose': 'plant_care',
        'query': 'Horticultural identification clues and container care for long, narrow green leaves',
        'evidence_indices': [0],
    }])
    topics = reason_scene_research_topics({'evidence': [
        'A potted balcony plant has long narrow green leaves.',
    ]}, client=model)
    assert len(topics) == 1
    assert topics[0][0] is ResearchPurpose.PLANT_CARE
    assert 'Observed context:' in topics[0][1]
    assert 'potted balcony plant' in topics[0][1]
    assert model.requests


def test_missing_nemotron_plant_topic_still_gets_bounded_reference_lookup():
    model = ResearchPlanner([])
    topics = reason_scene_research_topics({'evidence': [
        'A planter contains a leafy green vine beside the balcony railing.',
    ]}, client=model)
    assert len(topics) == 1
    assert topics[0][0] is ResearchPurpose.PLANT_CARE
    assert 'do not claim species confirmed' in topics[0][1]


def test_external_plant_references_do_not_claim_a_confirmed_species():
    provider = TavilyStub()
    sources = external_reference_for_scene({'evidence': [
        'An unidentified plant is growing in a balcony pot.',
    ]}, provider=provider)
    assert provider.requests[0].purpose is ResearchPurpose.PLANT_CARE
    assert len(sources[0]['sources']) == 1
    assert 'not confirmed visual identification' in sources[0]['note']


def test_latest_scanned_plant_research_is_saved_without_created_tasks():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with sessions.begin() as db:
        db.add(AutonomousScanJob(
            id='balcony-scan', household_id='home', media_id='photo-balcony',
            room_id='room-balcony', state='completed', attempts=1,
            next_attempt_at=now, updated_at=now, message='',
            review_summary={'evidence': [
                'A potted plant with pointed leaves is visible on the balcony.'
            ], 'created_count': 0, 'progress_results': {}}))
    provider = TavilyStub()
    orchestrator = HouseholdAutoOrchestrator(sessions, provider=provider,
        advice=lambda plan: {'source':'deterministic', 'selected_task_id':None,
                             'summary':'No active task', 'reason':'No task created'})
    result = orchestrator.after_scan('balcony-scan')
    assert result['status'] == 'completed'
    assert result['researched_tasks'] == 0
    assert result['source_count'] == 1
    assert result['scene_research'][0]['topic'] == 'plant_care'
    assert result['scene_research'][0]['sources'][0]['url'] == 'https://example.org/plant-care'
    with sessions() as db:
        saved = db.get(AutonomousScanJob, 'balcony-scan')
        assert saved.review_summary['automatic_coordination']['scene_research'][0]['sources']
    assert orchestrator.after_scan('balcony-scan') is None
    assert len(provider.requests) == 1
    engine.dispose()

"""Room classification and evidence-grounded handling of an unfamiliar laundry scene."""
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.coordination.auto_orchestration import scene_research_topics
from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService
from app.services.open_world_live import (
    ClaimVerdict, OpenWorldPlanner, OpenWorldVision, VisualClaim, VisualReview,
    VisualScene, corroborate_scene,
)
from app.services.open_world_planning import Evidence, SceneContext


class FakeVisionClient:
    def __init__(self, *answers):
        self.answers = iter(answers)
        self.instructions = []

    def ask(self, **kwargs):
        self.instructions.append(kwargs['instruction'])
        return next(self.answers)


def test_generic_other_cannot_be_persisted_as_a_verified_room():
    scene = VisualScene(room_category='Other', claims=[
        VisualClaim(id='e1', description='A pile of loose clothing is visible beside a washer.')])
    verified = VisualReview(room_supported=True, room_category='Other', claims=[
        ClaimVerdict(id='e1', supported=True)])
    context, evidence = corroborate_scene(scene, verified, 'photo')
    assert context.category is None
    assert not context.category_supported
    assert len(evidence) == 1


def test_independent_image_review_can_recover_a_laundry_label_from_other():
    primary = FakeVisionClient(
        {'room_category': 'Other', 'claims': [
            {'id': 'e1', 'description': 'A washing machine is installed next to a dryer.'}]},
        {'room_category': 'Laundry room', 'claims': [
            {'id': 'extra', 'description': 'A laundry counter is beside the washer.'}]},
    )
    reviewer = FakeVisionClient({'room_supported': True, 'room_category': 'Laundry room',
                                 'claims': [{'id': 'e1', 'supported': True}, {'id': 'e2', 'supported': True}]})
    additional = FakeVisionClient({'room_supported': True, 'room_category': 'Laundry room',
                                   'claims': [{'id': 'e1', 'supported': True}, {'id': 'e2', 'supported': True}]})
    vision = OpenWorldVision(primary, reviewer, additional)
    scene = vision.extract(b'photo', 'image/jpeg')
    assert scene.room_category == 'Laundry room'
    review = vision.verify(scene, b'photo', 'image/jpeg')
    context, evidence = corroborate_scene(scene, review, 'photo')
    assert context.category == 'Laundry room'
    assert context.category_supported
    assert len(evidence) == 2
    assert 'washer' in primary.instructions[0].lower()


def test_generic_demo_category_does_not_override_independent_image_review():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    jobs = AutonomousJobService(sessionmaker(engine, expire_on_commit=False))
    jobs.enroll('home', 'old', 'Kitchen')
    jobs.enqueue('home', 'new')
    photos = {'old': b'older-photo', 'new': b'new-photo'}

    class Media:
        def get_image(self, household, media_id):
            return SimpleNamespace(content_type='image/jpeg'), photos[media_id]

    def scan(**kwargs):
        return {'status': 'reviewed', 'room_category': 'Laundry room',
                'created': [], 'existing': [],
                'review_summary': {'room_category': 'Laundry room'}}

    catalog = {'older-photo': {'family': 'family-old', 'category': 'Kitchen'},
               'new-photo': {'family': 'family-new', 'category': 'Other'}}
    with patch('app.services.autonomous_jobs.verified_demo_scene',
               side_effect=lambda data: catalog.get(data.decode())):
        result = jobs.process_one(media=Media(), bridge=None, build_pipeline=lambda: None, scan=scan)
    assert result == 'completed'
    assert {room['room_category'] for room in jobs.rooms('home')} == {'Kitchen', 'Laundry room'}


def test_planner_considers_conditional_laundry_work_without_guessing_status_or_time():
    class PlannerClient:
        def __init__(self): self.prompt = ''
        def ask(self, *, instruction, payload):
            self.prompt = instruction
            return {'actions': []}

    client = PlannerClient()
    evidence = [Evidence(id='e1', provenance='visible', source_id='image',
                         description='Clothing is piled in a laundry basket near a washer.')]
    plan = OpenWorldPlanner(client).propose(
        evidence, SceneContext(category='Laundry room', category_supported=True),
        existing_tasks=[{'title': 'Clear walkway', 'action': 'Clear the walking path'}])
    assert not plan.actions
    prompt = client.prompt.lower()
    assert 'already clean' in prompt
    assert 'care labels' in prompt
    assert 'walkway' in prompt
    assert 'manufacturer' in prompt
    assert 'never make up a duration' in prompt


def test_tavily_duration_research_requires_verified_washer_and_laundry():
    from app.research.models import ResearchPurpose
    subjects = scene_research_topics({'evidence': [
        'Loose clothing is piled next to a washing machine in a laundry area.']})
    assert any(purpose == ResearchPurpose.HOUSEHOLD_CONTEXT and 'cycle duration' in query
               for purpose, query in subjects)
    unrelated = scene_research_topics({'evidence': ['Clothes are folded on a closet shelf.']})
    assert not any('cycle duration' in query for _, query in unrelated)


def test_nemotron_can_skip_general_web_search_but_not_sourced_wash_cycle_question():
    import json
    from app.coordination.auto_orchestration import reason_scene_research_topics
    from app.research.models import ResearchPurpose

    class EmptyTopicsClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        def create(self, **kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(
                finish_reason='stop', message=SimpleNamespace(content=json.dumps({'topics': []})))])

    topics = reason_scene_research_topics({'evidence': [
        'Several garments are placed on a shelf.',
        'A front-loading washing machine is installed next to the shelves.',
    ]}, client=EmptyTopicsClient())
    assert len(topics) == 1
    assert topics[0][0] is ResearchPurpose.HOUSEHOLD_CONTEXT
    assert 'cycle' in topics[0][1]

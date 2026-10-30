"""Offline checks for category-agnostic completeness and evidence-bound search."""
import json
from types import SimpleNamespace

from app.coordination.scene_focus import classify_scene_focus
from app.coordination.auto_orchestration import reason_scene_research_topics
from app.research.models import ResearchPurpose
from app.services.open_world_live import OpenWorldVision, VisualScene, VisualReview, ClaimVerdict, corroborate_scene


class FakeModel:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.requests = []
    def ask(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.answers)


class FakeResearchModel:
    def __init__(self, answer):
        self.requests = []
        self.answer = answer
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason='stop', message=SimpleNamespace(content=json.dumps(self.answer)))])


def test_any_reviewed_room_name_is_a_space_not_a_missed_taxonomy():
    for room in ('Mudroom', 'Attic', 'Sunroom', 'Front porch', 'Workshop', 'Greenhouse'):
        result = classify_scene_focus(['A fixed door and a wall are visible.'], room)
        assert result['focus'] == 'space'
        assert result['location_confirmed'] is False


def test_arbitrary_device_missed_condition_is_recovered_but_requires_review():
    model = FakeModel([
        {'room_category': 'Workshop', 'claims': [{'id': 'e1', 'description':'A drill press is on the bench.'}]},
        {'room_category': 'Workshop', 'claims': [{'id':'b1', 'description':'A warning icon appears on the battery monitor.'}]},
    ])
    scene = OpenWorldVision(model, None).extract(b'image', 'image/jpeg')
    assert len(model.requests) == 2
    assert 'completeness audit' in model.requests[1]['instruction']
    assert [x.id for x in scene.claims] == ['e1', 'e2']
    reviewed = VisualReview(room_supported=True, room_category='Workshop', claims=[
        ClaimVerdict(id='e1', supported=True), ClaimVerdict(id='e2', supported=False)])
    _, evidence = corroborate_scene(scene, reviewed, 'media')
    assert [x.id for x in evidence] == ['e1']


def test_generic_research_model_can_route_unlisted_household_problem():
    fake = FakeResearchModel({'topics': [{'purpose':'maintenance',
        'query':'What do battery monitor warning indicators generally mean for safe inspection?',
        'evidence_indices':[0]}]})
    topics = reason_scene_research_topics({'evidence':['A warning indicator is visible on a battery monitor.']},
                                         client=fake)
    assert len(topics) == 1
    assert topics[0][0] is ResearchPurpose.MAINTENANCE
    assert 'battery monitor' in topics[0][1]
    assert 'reviewed_observations' in fake.requests[0]['messages'][1]['content']


def test_generic_research_can_correctly_decline_unnecessary_lookups():
    fake = FakeResearchModel({'topics': []})
    assert reason_scene_research_topics({'evidence':['Three neatly stacked towels are visible on a shelf.']},
                                        client=fake) == []
    assert len(fake.requests) == 1


def test_generic_research_rejects_uncited_hallucination_and_falls_back():
    fake = FakeResearchModel({'topics': [{'purpose':'maintenance',
        'query':'Replace a nonexistent damaged roofing panel', 'evidence_indices':[13]}]})
    assert reason_scene_research_topics({'evidence':['A tidy attic is visible.']}, client=fake) == []


def test_generic_research_keeps_hazard_conservative():
    fake = FakeResearchModel({'topics': [{'purpose':'maintenance',
        'query':'How can a homeowner fix an active gas leak themselves?', 'evidence_indices':[0]}]})
    assert reason_scene_research_topics({'evidence':['A gas leak is suspected near the range.']}, client=fake) == []
    assert fake.requests == []


def test_unnamed_object_close_view_is_not_silently_discarded():
    focus = classify_scene_focus(['The thermostat has a cracked display.'], None)
    assert focus['focus'] == 'object'
    assert not focus['location_confirmed']


def test_completeness_pass_never_reuses_nonsequential_primary_claim_id():
    model = FakeModel([
        {'room_category':'Workshop', 'claims':[{'id':'e3', 'description':'A cracked device housing is visible.'}]},
        {'room_category':'Workshop', 'claims':[{'id':'extra', 'description':'The nearby charger LED is blinking.'}]},
    ])
    scene = OpenWorldVision(model, None).extract(b'photo', 'image/jpeg')
    assert len({x.id for x in scene.claims}) == 2


def test_research_sources_enter_planning_not_visible_evidence(monkeypatch):
    from app.services.open_world_live import preview_verified_scene, OpenWorldPlanner
    from app.coordination import auto_orchestration

    class Vision:
        def extract(self, image, media_type):
            return VisualScene(room_category='Workshop', claims=[
                {'id':'e1', 'description':'An unfamiliar warning symbol is visible on the charger.'}])
        def verify(self, scene, image, media_type):
            return VisualReview(room_supported=True, room_category='Workshop', claims=[ClaimVerdict(id='e1', supported=True)])

    class Client:
        def __init__(self): self.payloads=[]
        def ask(self, **kwargs):
            self.payloads.append(kwargs.get('payload'))
            return {'actions':[]}

    class Reviewer:
        def review(self, plan, original_media, media_type):
            from app.services.open_world_planning import IndependentPlanReview
            return IndependentPlanReview(reviews=[])

    monkeypatch.setenv('NEBIUS_API_KEY','fake')
    monkeypatch.setenv('TAVILY_API_KEY','fake')
    monkeypatch.setenv('HOMHIVE_IN_SCAN_RESEARCH','true')
    monkeypatch.setattr(auto_orchestration, 'external_reference_for_scene', lambda summary: [
        {'topic':'maintenance','sources':[{'title':'Reference','url':'https://example.org/reference',
            'excerpt':'Generic troubleshooting steps.'}]}])
    model=Client()
    result=preview_verified_scene(image=b'photo', media_type='image/jpeg',media_id='photo1',
        vision=Vision(),planner=OpenWorldPlanner(model),reviewer=Reviewer())
    assert len(result.corroborated_evidence) == 1
    assert result.corroborated_evidence[0].provenance == 'visible'
    assert model.payloads[0]['external_reference_knowledge'][0]['topic'] == 'maintenance'
    assert result.model_audit['preplan_research'][0]['sources'][0]['url'] == 'https://example.org/reference'


def test_research_stays_bounded_for_unlisted_type_and_trusted_sources():
    from app.coordination.auto_orchestration import external_reference_for_scene
    fake = FakeResearchModel({'topics':[]})
    class Provider:
        def __init__(self): self.requests=[]
        def search(self, request):
            self.requests.append(request)
            return SimpleNamespace(evidence=[SimpleNamespace(title='Safety guide',url='https://reference.test/guide',
                content='Do not use damaged electrical equipment.')])
    provider=Provider()
    result=external_reference_for_scene({'evidence':['The storage heater control displays an error icon.']}, provider=provider,
        reasoner=lambda evidence: [(ResearchPurpose.MAINTENANCE,'Safe general inspection of heater alert')])
    assert len(provider.requests) == 1
    assert result[0]['topic']=='maintenance'
    assert 'reference.test' in result[0]['sources'][0]['url']

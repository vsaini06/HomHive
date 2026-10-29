"""Verified two-image change evidence on the production preview path."""
import json
from types import SimpleNamespace

import pytest

from app.services.accuracy_models import AccuracyOpenAIJsonClient
from app.services.open_world_live import (
    OpenWorldVision, PreviewResult, VisualReview, VisualScene, _checked_pair_votes,
    preview_verified_scene,
)
from app.services.open_world_planning import (
    ActionProposal, ActionReview, IndependentPlanReview, ProposedPlan,
)


class TwoImageModel:
    def __init__(self, proposed, verified):
        self.proposed = proposed
        self.verified = verified
        self.calls = []

    def compare_changes(self, reference, ref_type, current, current_type, claims=None):
        self.calls.append((reference, ref_type, current, current_type, claims))
        return self.proposed if claims is None else self.verified

    def ask(self, **kwargs):
        return {'room_category':'kitchen','claims':[]}



class ClaudeJudge:
    def __init__(self, verified):
        self.verified = verified
        self.calls = []

    def verify_pair_changes(self, reference, ref_type, current, current_type, claims):
        self.calls.append((reference, ref_type, current, current_type, claims))
        return self.verified

    def ask(self, **kwargs):
        return {'room_supported': True, 'room_category': 'kitchen', 'claims': []}


class TerraJudge:
    def __init__(self, verified):
        self.verified = verified
        self.calls = []

    def compare_changes(self, reference, ref_type, current, current_type, claims):
        self.calls.append((reference, ref_type, current, current_type, claims))
        return self.verified

    def ask(self, **kwargs):
        return {'room_supported': True, 'room_category': 'kitchen', 'claims': []}


class ChangePlanner:
    def __init__(self): self.called = []
    def propose(self, evidence, scene):
        self.called.append(evidence)
        return ProposedPlan(scene=scene, evidence=evidence, actions=[ActionProposal(
            action_id='a1', title='Recheck cleared sink',
            action='Confirm dishes are removed from the kitchen sink',
            observation_location='kitchen', action_location='kitchen',
            supporting_evidence_ids=['p1'],
            verification_criteria='Current sink shows the dishes have been removed')])


class SafeReviewer:
    def review(self, plan, original_media, media_type):
        return IndependentPlanReview(reviews=[ActionReview(
            action_id='a1', directly_supported=True, feasible=True,
            no_unsupported_assumptions=True, safety_appropriate=True,
            explanation='Rechecking removal does not require adding unobserved chores')])


def vision(proposed=None, claude=None, terra=None):
    proposed = proposed if proposed is not None else {'changes': [{
        'id':'p1', 'change_type':'removal', 'description':'Dishes in reference kitchen sink are absent from current view',
    }]}
    claude = claude if claude is not None else {'changes':[{'id':'p1', 'supported':True}]}
    terra = terra if terra is not None else {'changes':[{'id':'p1', 'supported':True}]}
    return OpenWorldVision(TwoImageModel(proposed, None), ClaudeJudge(claude), TerraJudge(terra))


def test_verified_removal_survives_even_when_new_photo_has_no_standalone_claims():
    v = vision()
    planner = ChangePlanner()
    result = preview_verified_scene(image=b'now clean', media_type='image/jpeg', media_id='current',
        vision=v, planner=planner, reviewer=SafeReviewer(),
        reference_image=b'previous dirty', reference_media_type='image/png')
    assert [c.id for c in result.corroborated_evidence] == ['p1']
    assert result.corroborated_evidence[0].source_id == 'current'
    assert result.model_audit['paired_comparison']['proposed'][0]['accepted_as_action_evidence'] is True
    assert len(result.approved_actions) == 1
    assert v.independent.calls[0][:4] == (b'previous dirty', 'image/png', b'now clean', 'image/jpeg')
    assert v.additional.calls[0][4][0]['id'] == 'p1'


def test_review_disagreement_discards_change_and_never_invokes_planner():
    v = vision(claude={'changes':[{'id':'p1','supported':False}]})
    planner = ChangePlanner()
    result = preview_verified_scene(image=b'current', media_type='image/jpeg', media_id='new',
        vision=v, planner=planner, reviewer=SafeReviewer(),
        reference_image=b'reference', reference_media_type='image/jpeg')
    assert result.corroborated_evidence == []
    assert result.approved_actions == [] and not planner.called
    assert result.model_audit['paired_comparison']['proposed'][0]['claude_supported'] is False


def test_visibility_and_lighting_never_become_action_evidence_even_if_both_judges_agree():
    proposed = {'changes':[
        {'id':'p1','change_type':'visibility','description':'The corner is cropped out'},
        {'id':'p2','change_type':'lighting','description':'Lights are dimmer now'}]}
    agree = {'changes':[{'id':'p1','supported':True},{'id':'p2','supported':True}]}
    v = vision(proposed, agree, agree)
    changes, audit = v.compare_changes(b'ref','image/jpeg',b'new','image/jpeg')
    assert changes == [] and len(audit['proposed']) == 2
    assert not any(row['accepted_as_action_evidence'] for row in audit['proposed'])


@pytest.mark.parametrize('vote', [
    {'changes':[]},
    {'changes':[{'id':'p1','supported':'true'}]},
    {'changes':[{'id':'p1','supported':True},{'id':'p1','supported':True}]},
    {'changes':[{'id':'p2','supported':True}]},
    {'changes':'yes'},
])
def test_malformed_pair_judgments_fail_closed(vote):
    with pytest.raises(ValueError):
        _checked_pair_votes([{'id':'p1'}],vote)


def test_duplicate_ids_and_unreviewable_structure_fail_closed():
    proposed = {'changes':[
        {'id':'p1','change_type':'removal','description':'A visible item has been removed'},
        {'id':'p1','change_type':'removal','description':'Another visible item has been removed'}]}
    with pytest.raises(ValueError,match='Invalid pair'):
        vision(proposed).compare_changes(b'a','image/jpeg',b'b','image/jpeg')


def test_pair_change_adapter_sends_two_full_images_with_schema():
    calls = []
    class API:
        def create(self, **kw):
            calls.append(kw)
            return SimpleNamespace(status='completed',output_text=json.dumps({'changes':[]}))
    model = AccuracyOpenAIJsonClient(SimpleNamespace(responses=API()),'gpt-6-astra')
    assert model.compare_changes(b'photo1','image/jpeg',b'photo2','image/png') == {'changes':[]}
    call = calls[0]
    assert call['text']['format']['name'] == 'homhive_pair_changes'
    assert len([item for item in call['input'][0]['content'] if item['type']=='input_image']) == 2
    assert all(item['detail']=='high' for item in call['input'][0]['content'] if item['type']=='input_image')


def test_pair_review_adapter_never_asks_model_to_invent_new_changes():
    calls = []
    class API:
        def create(self, **kw):
            calls.append(kw)
            return SimpleNamespace(status='completed',output_text=json.dumps({'changes':[{'id':'p1','supported':True}]}))
    model=AccuracyOpenAIJsonClient(SimpleNamespace(responses=API()),'gpt-6.1-terra')
    changes=[{'id':'p1','change_type':'condition','description':'More dishes visible than before'}]
    result=model.compare_changes(b'one','image/jpeg',b'two','image/jpeg',claims=changes)
    assert result['changes'][0]['supported'] is True
    assert calls[0]['text']['format']['name'] == 'homhive_pair_review'
    assert 'proposed_changes' in calls[0]['input'][0]['content'][0]['text']


def test_non_accuracy_mode_remains_compatible_and_does_not_make_pair_claims():
    class SimpleVision:
        def extract(self, image, media_type): return VisualScene(claims=[])
        def verify(self, scene, image, media_type): return VisualReview(room_supported=False, claims=[])
    result=preview_verified_scene(image=b'now', media_type='image/jpeg', media_id='m',
        vision=SimpleVision(), planner=ChangePlanner(), reviewer=SafeReviewer(),
        reference_image=b'before', reference_media_type='image/jpeg')
    assert result.model_audit['paired_comparison']['status']=='unsupported_in_current_model_mode'
    assert result.corroborated_evidence == []


def test_pair_provider_failure_is_visible_but_existing_single_frame_path_continues():
    class BrokenVision:
        def extract(self, image, media_type):
            return VisualScene(room_category='kitchen', claims=[{
                'id':'e1','description':'Dirty dishes visible inside the sink'}])
        def verify(self, scene, image, media_type):
            return VisualReview(room_supported=True, room_category='kitchen',
                claims=[{'id':'e1','supported':True}])
        def compare_changes(self, *args):
            raise TimeoutError('provider not available')
    class Planner:
        def propose(self, evidence, scene):
            return ProposedPlan(scene=scene,evidence=evidence,actions=[])
    class NoActionReviewer:
        def review(self, plan, original_media, media_type):
            return IndependentPlanReview(reviews=[])
    result=preview_verified_scene(image=b'new',media_type='image/jpeg',media_id='media',
        vision=BrokenVision(),planner=Planner(),reviewer=NoActionReviewer(),
        reference_image=b'old',reference_media_type='image/jpeg')
    assert [e.id for e in result.corroborated_evidence] == ['e1']
    assert result.model_audit['paired_comparison'] == {'status':'unavailable','error_type':'TimeoutError'}


def test_real_accuracy_room_pair_uses_shared_json_parser():
    """The accuracy adapter short-circuits the legacy chat parser branch."""
    from app.vision.autonomous_api import verify_room_pair

    class AccuratePrimary:
        def compare_rooms(self, first, first_type, second, second_type):
            assert first == b"before" and second == b"after"
            return {"same_physical_room": True, "explanation": "Same fixed garage walls"}

    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"stop_reason": "end_turn", "content": [{"type": "text", "text":
                '{"same_physical_room":true,"explanation":"Same garage fixtures"}'}]}

    class FakeHTTP:
        def post(self, url, *, json, headers):
            assert url.endswith('/messages')
            assert json["output_config"]["format"]["type"] == "json_schema"
            assert len([block for block in json["messages"][0]["content"] if block["type"] == "image"]) == 2
            return FakeResponse()

    vision = SimpleNamespace(primary=AccuratePrimary(), independent=SimpleNamespace(
        client=FakeHTTP(), model="claude-opus-5-5", key="redacted", strict_structure=True))
    assert verify_room_pair(vision, b"before", "image/jpeg", b"after", "image/jpeg") is True


def test_real_accuracy_room_pair_requires_both_models_to_match():
    from app.vision.autonomous_api import verify_room_pair

    class Primary:
        def compare_rooms(self, *args):
            return {"same_physical_room": False, "explanation": "Different fixtures"}

    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"content": [{"type": "text", "text":
                '{"same_physical_room":true,"explanation":"Same garage fixtures"}'}]}

    class HTTP:
        def post(self, *args, **kwargs): return FakeResponse()

    vision = SimpleNamespace(primary=Primary(), independent=SimpleNamespace(
        client=HTTP(), model="claude-opus-5-5", key="redacted", strict_structure=False))
    assert verify_room_pair(vision, b"before", "image/jpeg", b"after", "image/jpeg") is False

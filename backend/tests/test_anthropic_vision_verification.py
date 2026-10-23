import json
from types import SimpleNamespace

from app.vision.anthropic_verification import AnthropicImageVerifier
from app.vision.service import VisionObservationService
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.vision.provider import VisionCandidate, VisionExtraction
from app.models import ConditionType
from app.vision.verification import IndependentReview, VerifiedClaim


def prediction():
    return VisionExtraction(candidates=[VisionCandidate(category=ConditionType.LAUNDRY_LOAD, value=.8, location='unknown', visible_evidence='basket')], needs_review=False, space_category='laundry_room')


def review(supported=True):
    return IndependentReview(space_category='laundry_room', room_supported=True, claims=[VerifiedClaim(category='laundry_load', visible=supported, evidence_supported=supported, workload_supported=supported)])


class FakeMedia:
    def get_image(self, household_id, media_id):
        return SimpleNamespace(content_type='image/jpeg'), b'abc'


class Primary:
    calls = 0
    def extract(self, *args):
        self.calls += 1
        return prediction()


class Reviewer:
    def __init__(self, supported=True):
        self.supported = supported
        self.calls = 0
    def review(self, *args):
        self.calls += 1
        return review(self.supported)


def test_three_model_agreement_and_disagreement():
    primary = Primary()
    extra = Reviewer()
    service = VisionObservationService(FakeMedia(), primary, InMemoryObservationRepository(), verifier=Reviewer(), additional_verifier=extra)
    result, saved = service.extract_and_store('house', 'image', 'unknown')
    assert len(saved) == 1 and saved[0].metadata['ai_verification'] == 'multi_model_corroborated'
    assert extra.calls == 1
    result, saved = VisionObservationService(FakeMedia(), Primary(), InMemoryObservationRepository(), verifier=Reviewer(), additional_verifier=Reviewer(False)).extract_and_store('house', 'image', 'unknown')
    assert result.needs_review and not saved


def test_anthropic_receives_original_image():
    recorded = {}
    class Client:
        def post(self, url, **kwargs):
            recorded.update(kwargs)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'content':[{'type':'text','text': review().model_dump_json()}]})
    result = AnthropicImageVerifier(model='test', api_key='testkey', client=Client()).review(b'abc','image/jpeg',prediction())
    assert result.room_supported
    data=recorded['json']['messages'][0]['content'][1]['source']
    assert data['media_type'] == 'image/jpeg' and data['data'] == 'YWJj'
    assert recorded['headers']['x-api-key'] == 'testkey'

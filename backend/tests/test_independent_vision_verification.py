from types import SimpleNamespace

from app.vision.provider import VisionExtraction, VisionCandidate, SpaceCategory
from app.vision.verification import IndependentReview, VerifiedClaim, corroborate, OpenAIImageVerifier
from app.vision.service import VisionObservationService
from app.models import ConditionType
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository


def prediction():
    return VisionExtraction(candidates=[VisionCandidate(category=ConditionType.LAUNDRY_LOAD, value=.8, location='unknown', visible_evidence='Visible basket')], needs_review=False, space_category=SpaceCategory.LAUNDRY_ROOM)


def review(category='laundry_room', support=True):
    return IndependentReview(space_category=category, room_supported=support, claims=[VerifiedClaim(category='laundry_load', visible=True, evidence_supported=True, workload_supported=True)])


def test_independent_review_requires_matching_room_and_visual_claims():
    assert corroborate(prediction(), review())
    assert not corroborate(prediction(), review('kitchen'))
    assert not corroborate(prediction(), review(support=False))
    assert not corroborate(prediction(), IndependentReview(space_category='laundry_room', room_supported=True, claims=[]))
    assert not corroborate(prediction(), IndependentReview(space_category='laundry_room', room_supported=True, claims=[VerifiedClaim(category='laundry_load',visible=True,evidence_supported=False,workload_supported=True)]))


class Media:
    def get_image(self, household_id, media_id):
        return SimpleNamespace(content_type='image/jpeg'), b'fake-image'

class Provider:
    def extract(self, image, content_type, location):
        return prediction()

class Verifier:
    def __init__(self, supported=True):
        self.supported=supported
        self.calls=0
    def review(self, image, content_type, proposed):
        assert image == b'fake-image'
        self.calls+=1
        return review(support=self.supported)


def test_corroborated_extract_preserves_distinction_from_human_confirmation():
    repo=InMemoryObservationRepository()
    v=Verifier()
    svc=VisionObservationService(Media(),Provider(),repo,verifier=v)
    extracted, stored=svc.extract_and_store('home','media','unknown')
    assert len(stored)==1
    assert stored[0].confidence is None
    assert stored[0].metadata['ai_verification']=='independently_corroborated'
    assert stored[0].metadata['space_identity_status']=='unresolved'
    svc.extract_and_store('home','media','unknown')
    assert v.calls==1


def test_disagreement_does_not_create_trusted_or_unconfirmed_observation():
    repo=InMemoryObservationRepository()
    result,stored=VisionObservationService(Media(),Provider(),repo,verifier=Verifier(False)).extract_and_store('home','media','unknown')
    assert result.needs_review and not stored and not repo.list_observations('home')


def test_openai_verifier_receives_image_and_model_claims():
    captured={}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"space_category":"laundry_room","room_supported":true,"claims":[{"category":"laundry_load","visible":true,"evidence_supported":true,"workload_supported":true}]}'))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result=OpenAIImageVerifier(model='test-model',client=client).review(b'abc','image/jpeg',prediction())
    assert corroborate(prediction(),result)
    content=captured['messages'][1]['content']
    assert content[1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert 'laundry_load' in content[0]['text']


def test_required_review_without_credentials_fails_closed():
    repo=InMemoryObservationRepository()
    result, saved=VisionObservationService(Media(),Provider(),repo,require_verification=True).extract_and_store('home','media','unknown')
    assert result.needs_review
    assert saved == []

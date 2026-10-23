from types import SimpleNamespace

from app.vision.provider import NebiusVisionProvider, SpaceCategory
from app.vision.service import VisionObservationService
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository


class FakeClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))])))


def test_category_hint_does_not_invent_specific_room_identity():
    response = ('{"candidates":[{"category":"dish_load","value":0.8,'
        '"location":"unknown","visible_evidence":"Stacked dishes in a visible sink"}],'
        '"needs_review":false,"space_category":"kitchen"}')
    provider = NebiusVisionProvider(client=FakeClient(response))
    class Media:
        def get_image(self, household, media_id):
            return SimpleNamespace(content_type='image/jpeg'), b'\xff\xd8\xffcontent'
    observations=InMemoryObservationRepository()
    result, created = VisionObservationService(Media(), provider, observations, verifier=AcceptingImageReviewer(), additional_verifier=AcceptingImageReviewer(), require_verification=True).extract_and_store('home','photo-1','unknown')
    assert result.space_category == SpaceCategory.KITCHEN
    assert created[0].location == 'kitchen'
    assert created[0].metadata['location_provenance'] == 'scene_inferred_category'
    assert created[0].metadata['space_category_hint'] == 'kitchen'
    assert created[0].metadata['space_identity_status'] == 'unresolved'
    assert created[0].confidence is None


def test_unrecognizable_room_remains_unknown():
    response='{"candidates":[],"needs_review":true,"space_category":"unknown"}'
    provider = NebiusVisionProvider(client=FakeClient(response))
    class Media:
        def get_image(self, household, media_id):
            return SimpleNamespace(content_type='image/jpeg'), b'\xff\xd8\xffcontent'
    result, created = VisionObservationService(Media(), provider, InMemoryObservationRepository()).extract_and_store('home','photo-1','unknown')
    assert not created and result.needs_review
    assert result.space_category == SpaceCategory.UNKNOWN


def test_laundry_scene_sets_category_without_claiming_room_identity():
    response = ('{"candidates":[{"category":"laundry_load","value":0.75,'
        '"location":"unknown","visible_evidence":"Laundry baskets and scattered clothes"}],'
        '"needs_review":false,"space_category":"laundry_room"}')
    class Media:
        def get_image(self, household, media_id):
            return SimpleNamespace(content_type='image/jpeg'), b'\xff\xd8\xffcontent'
    storage = InMemoryObservationRepository()
    service = VisionObservationService(Media(), NebiusVisionProvider(client=FakeClient(response)), storage, verifier=AcceptingImageReviewer(), additional_verifier=AcceptingImageReviewer(), require_verification=True)
    first, created = service.extract_and_store('home', 'laundry-photo', 'unknown')
    assert first.space_category == SpaceCategory.LAUNDRY_ROOM
    assert created[0].location == 'laundry_room'
    assert created[0].metadata['space_identity_status'] == 'unresolved'
    again, repeated = service.extract_and_store('home', 'laundry-photo', 'unknown')
    assert again.space_category == SpaceCategory.LAUNDRY_ROOM
    assert repeated[0].id == created[0].id
    assert len(storage.list_observations('home')) == 1


class AcceptingImageReviewer:
    """Deterministic positive review fixture; live services require real reviewers."""
    def review(self, image, content_type, proposed):
        from app.vision.verification import IndependentReview, VerifiedClaim
        from app.vision.provider import SpaceCategory
        return IndependentReview(
            space_category=proposed.space_category or SpaceCategory.UNKNOWN,
            room_supported=(proposed.space_category or SpaceCategory.UNKNOWN) != SpaceCategory.UNKNOWN,
            claims=[VerifiedClaim(category=c.category.value, visible=True,
                                  evidence_supported=True, workload_supported=True)
                    for c in proposed.candidates],
        )

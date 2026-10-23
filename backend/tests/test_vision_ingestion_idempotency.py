from app.vision.service import VisionObservationService
from app.vision.provider import VisionExtraction, VisionCandidate
from app.models import ConditionType
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository


class Media:
    def get_image(self, household_id, media_id):
        from types import SimpleNamespace
        return SimpleNamespace(content_type='image/png'), b'\x89PNG\r\n\x1a\nimage'


class Provider:
    calls = 0
    def extract(self, image, content_type, location):
        self.calls += 1
        return VisionExtraction(candidates=[VisionCandidate(
            category=ConditionType.DISH_LOAD, value=0.7, location=location,
            visible_evidence='Visible stacked dishes'
        )], needs_review=False)


def test_same_media_never_reprocesses_or_duplicates_unconfirmed_evidence():
    observations = InMemoryObservationRepository()
    provider = Provider()
    service = VisionObservationService(Media(), provider, observations)
    first = service.extract_and_store('home', 'same-media', 'kitchen')
    second = service.extract_and_store('home', 'same-media', 'kitchen')
    assert first[1][0].id == second[1][0].id
    assert provider.calls == 1
    assert second[1][0].confidence is None
    assert len(observations.list_observations('home')) == 1
    assert service.extract_and_store('another-home', 'same-media', 'kitchen')[1][0].id != first[1][0].id

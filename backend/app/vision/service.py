from uuid import uuid4

from app.media.service import MediaService
from app.models import Observation, ObservationSource
from app.repositories.observation_storage import ObservationStorage

from .provider import VisionExtraction, VisionProvider


class VisionObservationService:
    def __init__(self, media: MediaService, provider: VisionProvider, observations: ObservationStorage):
        self._media = media
        self._provider = provider
        self._observations = observations

    def extract_and_store(self, household_id: str, media_id: str, location: str) -> tuple[VisionExtraction, list[Observation]] | None:
        stored = self._media.get_image(household_id, media_id)
        if stored is None:
            return None
        info, image = stored
        result = self._provider.extract(image, info.content_type, location)
        if result.needs_review:
            return result, []
        created = []
        for candidate in result.candidates:
            observation = Observation(
                id=str(uuid4()),
                source=ObservationSource.PHOTO,
                location=candidate.location,
                category=candidate.category,
                value=candidate.value,
                confidence=None,
                metadata={"media_id": media_id, "visible_evidence": candidate.visible_evidence},
            )
            created.append(self._observations.add_observation(household_id, observation))
        return result, created

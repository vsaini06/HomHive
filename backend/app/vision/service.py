from uuid import uuid5, NAMESPACE_URL

from app.media.service import MediaService
from app.models import Observation, ObservationSource
from app.repositories.observation_storage import ObservationStorage

from .provider import VisionCandidate, VisionExtraction, VisionProvider


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
        # Once an image has been extracted, reuse the original unconfirmed evidence.
        # Do not silently convert those predictions to trusted household state.
        previous = [o for o in self._observations.list_observations(household_id)
                    if o.metadata.get("media_id") == media_id]
        if previous:
            hint = previous[0].metadata.get("space_category_hint")
            from .provider import SpaceCategory
            known_category = SpaceCategory(hint) if hint in SpaceCategory._value2member_map_ else SpaceCategory.UNKNOWN
            return VisionExtraction(
                candidates=[VisionCandidate(
                    category=o.category, value=o.value, location=o.location,
                    visible_evidence=str(o.metadata.get("visible_evidence") or "Previously recorded evidence"),
                ) for o in previous], needs_review=False,
                space_category=known_category,
            ), previous
        result = self._provider.extract(image, info.content_type, location)
        if result.needs_review:
            return result, []
        # Category and physical room identity are distinct. A category is safe
        # to display as a provisional space, but never verifies which room it is.
        inferred = (result.space_category.value if result.space_category and
                    result.space_category.value != "unknown" else None)
        supplied = location.strip() if location.strip() != "unknown" else None
        display_location = supplied or inferred or "unknown"
        created = []
        for candidate in result.candidates:
            # Stable identity per media/category protects retries from duplicating evidence.
            observation_id = str(uuid5(NAMESPACE_URL, f"{household_id}:{media_id}:{candidate.category.value}"))
            prior = self._observations.find_observation(household_id, observation_id)
            if prior is not None:
                created.append(prior)
                continue
            observation = Observation(
                id=observation_id,
                source=ObservationSource.PHOTO,
                location=display_location,
                category=candidate.category,
                value=candidate.value,
                confidence=None,
                metadata={"media_id": media_id, "visible_evidence": candidate.visible_evidence,
                          "space_category_hint": result.space_category.value if result.space_category else "unknown",
                          "space_identity_status": "provided_unverified" if supplied else "unresolved",
                          "location_provenance": "user_supplied" if supplied else
                              ("scene_inferred_category" if inferred else "unknown")},
            )
            created.append(self._observations.add_observation(household_id, observation))
        return result, created

from app.models import Observation, ObservationSource, ConditionType
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.services.observation_review import confirm_observation


def test_confirmation_preserves_visual_evidence_and_room_uncertainty():
    storage = InMemoryObservationRepository()
    original = Observation(id="scene-1", source=ObservationSource.PHOTO,
                           location="laundry_room", category=ConditionType.LAUNDRY_LOAD,
                           value=0.75, confidence=None,
                           metadata={"media_id": "media-1", "visible_evidence": "Clothes on the floor",
                                     "space_category_hint": "laundry_room",
                                     "space_identity_status": "unresolved",
                                     "location_provenance": "scene_inferred_category"})
    storage.add_observation("home", original)
    confirmed = confirm_observation("home", original.id, 0.75, storage)
    assert confirmed.location == "laundry_room"
    assert confirmed.metadata["visible_evidence"] == "Clothes on the floor"
    assert confirmed.metadata["space_identity_status"] == "unresolved"
    assert confirmed.metadata["source_media_id"] == "media-1"
    assert confirmed.confidence == 1.0

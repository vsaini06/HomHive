from types import SimpleNamespace
from unittest.mock import Mock

from app.vision.provider import VisionCandidate, VisionExtraction, SpaceCategory
from app.vision.service import VisionObservationService
from app.models import ConditionType
from app.vision.verification import IndependentReview, VerifiedClaim


def _result(needs_review=True, candidates=True):
    return VisionExtraction(
        candidates=[VisionCandidate(category=ConditionType.DISH_LOAD, value=0.7, location="unknown",
                                    visible_evidence="Visible dishes in sink")] if candidates else [],
        needs_review=needs_review, space_category=SpaceCategory.KITCHEN,
    )


def _review():
    return IndependentReview(space_category=SpaceCategory.KITCHEN, room_supported=True, claims=[VerifiedClaim(
        category="dish_load", visible=True, evidence_supported=True,
        workload_supported=True,
    )])


def _setup(result, reviewer=None, additional=None, required=True):
    media = Mock()
    media.get_image.return_value = (SimpleNamespace(content_type="image/jpeg"), b"image-data")
    provider = Mock()
    provider.extract.return_value = result
    storage = Mock()
    storage.list_observations.return_value = []
    storage.find_observation.return_value = None
    storage.add_observation.side_effect = lambda home, obs: obs
    svc = VisionObservationService(media, provider, storage, verifier=reviewer,
                                   additional_verifier=additional, require_verification=required)
    return svc, storage


def test_primary_review_required_goes_to_both_visual_reviewers_before_persistence():
    primary = Mock()
    primary.review.return_value = _review()
    secondary = Mock()
    secondary.review.return_value = _review()
    svc, storage = _setup(_result(), primary, secondary)
    extraction, observations = svc.extract_and_store("h1", "media1", "unknown")
    assert not extraction.needs_review
    assert len(observations) == 1
    assert observations[0].metadata["ai_verification"] == "multi_model_corroborated"
    primary.review.assert_called_once()
    secondary.review.assert_called_once()
    assert primary.review.call_args.args[0] == b"image-data"
    assert secondary.review.call_args.args[0] == b"image-data"


def test_review_required_without_verifier_does_not_persist():
    svc, storage = _setup(_result(), reviewer=None)
    extraction, observations = svc.extract_and_store("h1", "media1", "unknown")
    assert extraction.needs_review and observations == []
    storage.add_observation.assert_not_called()


def test_review_disagreement_keeps_evidence_unresolved():
    primary = Mock()
    primary.review.return_value = _review()
    secondary = Mock()
    secondary.review.return_value = IndependentReview(space_category=SpaceCategory.KITCHEN, room_supported=False, claims=[])
    svc, storage = _setup(_result(), primary, secondary)
    extraction, observations = svc.extract_and_store("h1", "media1", "unknown")
    assert extraction.needs_review and observations == []
    storage.add_observation.assert_not_called()


def test_no_candidates_never_calls_reviewers():
    primary = Mock()
    svc, storage = _setup(_result(candidates=False), primary)
    extraction, observations = svc.extract_and_store("h1", "media1", "unknown")
    assert extraction.needs_review and observations == []
    primary.review.assert_not_called()
    storage.add_observation.assert_not_called()

from types import SimpleNamespace

from app.models import ConditionType
from app.repositories.in_memory_observation_repository import InMemoryObservationRepository
from app.vision.provider import VisionCandidate, VisionExtraction
from app.vision.service import VisionObservationService
from app.vision.verification import IndependentReview, VerifiedClaim


class Media:
    def get_image(self, household_id, media_id):
        return SimpleNamespace(content_type='image/jpeg'), b'image'


class Primary:
    def extract(self, *args):
        return VisionExtraction(space_category='kitchen', needs_review=True, candidates=[
            VisionCandidate(category=ConditionType.DISH_LOAD, value=.8, location='unknown', visible_evidence='Dishes in sink'),
            VisionCandidate(category=ConditionType.PLANT_CONDITION, value=.4, location='unknown', visible_evidence='Plant on counter'),
        ])


class Reviewer:
    def __init__(self, *, plant=True, fails=False):
        self.calls = 0
        self.plant = plant
        self.fails = fails

    def review(self, image, content_type, proposed):
        self.calls += 1
        assert image == b'image'
        if self.fails:
            raise TimeoutError('Secret provider response should not be displayed')
        return IndependentReview(space_category='kitchen', room_supported=True, claims=[
            VerifiedClaim(category='dish_load', visible=True, evidence_supported=True, workload_supported=True),
            VerifiedClaim(category='plant_condition', visible=self.plant, evidence_supported=self.plant, workload_supported=self.plant),
        ])


def test_both_reviewers_run_when_first_disagrees_and_partial_claim_survives():
    a, b = Reviewer(plant=False), Reviewer(plant=True)
    repo = InMemoryObservationRepository()
    service = VisionObservationService(Media(), Primary(), repo, verifier=a, additional_verifier=b, require_verification=True)
    result, observations = service.extract_and_store('household', 'photo', 'unknown')
    assert (a.calls, b.calls) == (1, 1)
    assert result.needs_review
    assert len(observations) == 1
    assert observations[0].category == ConditionType.DISH_LOAD
    assert observations[0].confidence is None
    assert result._verification_diagnostics['overall'] == 'partially_corroborated'
    assert [x['status'] for x in result._verification_diagnostics['claims']] == ['corroborated', 'disputed']

    service.extract_and_store('household', 'photo', 'unknown')
    assert (a.calls, b.calls) == (1, 1)


def test_review_failure_is_not_classified_as_disagreement(caplog):
    a, b = Reviewer(fails=True), Reviewer()
    repo = InMemoryObservationRepository()
    service = VisionObservationService(Media(), Primary(), repo, verifier=a, additional_verifier=b, require_verification=True)
    result, observations = service.extract_and_store('household', 'photo', 'unknown')
    assert (a.calls, b.calls) == (1, 1)
    assert result.needs_review and not observations
    assert result._verification_diagnostics['openai'] == 'provider_error'
    assert result._verification_diagnostics['anthropic'] == 'completed'
    assert result._verification_diagnostics['overall'] == 'provider_failure_or_missing_review'
    assert 'Secret provider response' not in caplog.text
    assert not repo.list_observations('household')


def test_missing_second_reviewer_fails_closed_in_required_mode():
    result, observations = VisionObservationService(
        Media(), Primary(), InMemoryObservationRepository(),
        verifier=Reviewer(), require_verification=True,
    ).extract_and_store('household', 'photo', 'unknown')
    assert result.needs_review and not observations
    assert result._verification_diagnostics['overall'] == 'missing_required_reviewers'


def test_safe_failure_category_reports_authentication_without_leaking_body():
    import httpx
    from app.vision.service import _safe_reviewer_failure_category
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(401, request=req, text="SECRET_PROVIDER_DETAIL")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        assert _safe_reviewer_failure_category(exc) == "authentication_or_permission"


def test_failure_category_in_diagnostics_for_anthropic():
    import httpx
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    class BadAnthropic:
        def review(self, *_):
            httpx.Response(401, request=request).raise_for_status()
    result, observations = VisionObservationService(
        Media(), Primary(), InMemoryObservationRepository(),
        verifier=Reviewer(), additional_verifier=BadAnthropic(), require_verification=True,
    ).extract_and_store("household", "photo", "unknown")
    assert not observations
    assert result._verification_diagnostics["anthropic"] == "provider_error"
    assert result._verification_diagnostics["anthropic_error_category"] == "authentication_or_permission"
    assert result._verification_diagnostics["overall"] == "provider_failure_or_missing_review"

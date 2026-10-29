from uuid import uuid5, NAMESPACE_URL
import json

import httpx
from pydantic import ValidationError

from app.media.service import MediaService
from app.models import Observation, ObservationSource
from app.repositories.observation_storage import ObservationStorage

from .provider import VisionCandidate, VisionExtraction, VisionProvider


def _safe_reviewer_failure_category(exc: Exception) -> str:
    """Classify failures without exposing credentials, request data, or response bodies."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return "authentication_or_permission"
        if status == 402:
            return "billing_or_credits"
        if status == 429:
            return "rate_limit"
        if status == 404:
            return "model_or_endpoint_unavailable"
        if status == 400:
            return "invalid_request"
        if status >= 500:
            return "provider_server_error"
        return "provider_http_error"
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return "timeout"
    if isinstance(exc, httpx.RequestError):
        return "network_error"
    if isinstance(exc, (json.JSONDecodeError, ValidationError)):
        return "invalid_review_response"
    if isinstance(exc, ValueError):
        return "invalid_or_incomplete_response"
    return "unexpected_review_error"


class VisionObservationService:
    def __init__(self, media: MediaService, provider: VisionProvider, observations: ObservationStorage, verifier=None, require_verification: bool = False, additional_verifier=None):
        self._media = media
        self._provider = provider
        self._observations = observations
        self._verifier = verifier
        self._require_verification = require_verification
        self._additional_verifier = additional_verifier

    def extract_and_store(self, household_id: str, media_id: str, location: str) -> tuple[VisionExtraction, list[Observation]] | None:
        stored = self._media.get_image(household_id, media_id)
        if stored is None:
            return None
        info, image = stored


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


        if not result.candidates:
            result._verification_diagnostics = {
                "primary": "no_candidates", "openai": "not_called",
                "anthropic": "not_called", "claims": [],
            }
            return result.model_copy(update={"needs_review": True}), []

        reviewers = (("openai", self._verifier), ("anthropic", self._additional_verifier))
        diagnostics = {"primary": "candidates_present", "openai": "not_configured",
                       "anthropic": "not_configured", "claims": []}

        if self._require_verification and (self._verifier is None or self._additional_verifier is None):
            diagnostics["overall"] = "missing_required_reviewers"
            result._verification_diagnostics = diagnostics
            return result.model_copy(update={"needs_review": True}), []
        successful_reviews = []
        for name, reviewer in reviewers:
            if reviewer is None:
                continue
            try:
                review = reviewer.review(image, info.content_type, result)
            except Exception as exc:


                import logging
                logging.getLogger(__name__).warning(
                    "Vision reviewer failure: provider=%s error_type=%s",
                    name, type(exc).__name__,
                )
                diagnostics[name] = "provider_error"
                diagnostics[f"{name}_error_category"] = _safe_reviewer_failure_category(exc)
            else:
                successful_reviews.append(review)
                diagnostics[name] = "completed"



        required = [name for name, provider in reviewers if provider is not None]
        if self._require_verification and len(required) != 2:
            diagnostics["overall"] = "missing_required_reviewers"
            result._verification_diagnostics = diagnostics
            return result.model_copy(update={"needs_review": True}), []
        if not required or len(successful_reviews) != len(required):
            diagnostics["overall"] = "provider_failure_or_missing_review"
            result._verification_diagnostics = diagnostics
            return result.model_copy(update={"needs_review": True}), []

        from .reconciliation import supported_claims
        accepted_candidates, claim_decisions, room_supported = supported_claims(
            result, tuple(successful_reviews)
        )
        diagnostics["claims"] = [
            {"category": d.category, "status": d.status, "reason": d.reason}
            for d in claim_decisions
        ]
        diagnostics["room"] = "corroborated" if room_supported else "unresolved"
        diagnostics["overall"] = (
            "corroborated" if len(accepted_candidates) == len(result.candidates)
            else "partially_corroborated" if accepted_candidates else "unresolved"
        )
        if not room_supported:


            from .provider import SpaceCategory
            result = result.model_copy(update={"space_category": SpaceCategory.UNKNOWN})
        result = result.model_copy(update={
            "candidates": accepted_candidates,
            "needs_review": len(accepted_candidates) != len(claim_decisions),
        })
        result._verification_diagnostics = diagnostics
        if not accepted_candidates:
            return result, []


        inferred = (result.space_category.value if result.space_category and
                    result.space_category.value != "unknown" else None)
        supplied = location.strip() if location.strip() != "unknown" else None
        display_location = supplied or inferred or "unknown"
        created = []
        for candidate in result.candidates:

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
                          "ai_verification": ("multi_model_corroborated" if self._additional_verifier is not None else "independently_corroborated") if self._verifier is not None else "not_performed",
                          "ai_verification_scope": "claim_level",
                          "location_provenance": "user_supplied" if supplied else
                              ("scene_inferred_category" if inferred else "unknown")},
            )
            created.append(self._observations.add_observation(household_id, observation))
        return result, created

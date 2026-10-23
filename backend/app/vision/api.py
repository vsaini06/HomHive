import hmac
from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .service import VisionObservationService


class VisionRequest(BaseModel):
    location: str = Field(min_length=1, max_length=255)


def build_vision_router(service: VisionObservationService, household_tokens: Mapping[str, str]) -> APIRouter:
    router = APIRouter(prefix="/households/{household_id}/media", tags=["vision"])
    bearer = HTTPBearer(auto_error=False)

    @router.post("/{media_id}/observations")
    def extract_observations(
        household_id: str,
        media_id: str,
        request: VisionRequest,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        expected = household_tokens.get(household_id)
        if expected is None or credentials is None or not hmac.compare_digest(credentials.credentials, expected):
            raise HTTPException(status_code=403, detail="Access denied")
        try:
            result = service.extract_and_store(household_id, media_id, request.location)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Vision extraction failed validation") from exc
        if result is None:
            raise HTTPException(status_code=404, detail="Media not found")
        extraction, observations = result
        return {"needs_review": extraction.needs_review, "observations": [observation.model_dump(mode="json") for observation in observations],
                "verification": extraction._verification_diagnostics}

    return router

from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException

from app.api.household_auth import build_household_authorizer

from .models import ResearchRequest
from .service import ResearchService


def build_research_router(
    service: ResearchService,
    household_tokens: Mapping[str, str],
) -> APIRouter:
    router = APIRouter(prefix="/households/{household_id}", tags=["research"])
    authorize = build_household_authorizer(household_tokens)

    @router.post("/research")
    def research(
        household_id: str,
        request: ResearchRequest,
        _: None = Depends(authorize),
    ):
        try:
            result = service.research(household_id, request)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail="Research provider unavailable") from exc
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="Research provider returned invalid data") from exc
        return result.model_dump(mode="json")

    return router

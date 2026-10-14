from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.api.household_auth import build_household_authorizer
from app.research import ResearchRequest

from .models import PlanningContext
from .service import PlanningService


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context: PlanningContext
    research: list[ResearchRequest] = Field(default_factory=list, max_length=5)


def build_planning_router(
    service: PlanningService,
    household_tokens: Mapping[str, str],
) -> APIRouter:
    router = APIRouter(prefix="/households/{household_id}", tags=["planning"])
    authorize = build_household_authorizer(household_tokens)

    @router.post("/plan")
    def create_plan(
        household_id: str,
        request: PlanRequest,
        _: None = Depends(authorize),
    ):
        try:
            plan, feasibility, research = service.create_plan(
                household_id,
                request.context,
                request.research,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail="External research unavailable") from exc
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return {
            "plan": plan.model_dump(mode="json"),
            "feasibility": [item.model_dump(mode="json") for item in feasibility],
            "research": [item.model_dump(mode="json") for item in research],
        }

    return router

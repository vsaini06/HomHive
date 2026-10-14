from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.repositories.observation_storage import ObservationStorage
from app.repositories.task_storage import TaskStorage
from app.services.household_intelligence import refresh_household_intelligence
from app.services.observation_review import confirm_observation

from .household_auth import build_household_authorizer


class ObservationReviewRequest(BaseModel):
    confirmed_value: float = Field(ge=0.0, le=1.0)


def build_intelligence_router(
    observation_storage: ObservationStorage,
    task_storage: TaskStorage,
    household_tokens: Mapping[str, str],
) -> APIRouter:
    router = APIRouter(prefix="/households/{household_id}", tags=["intelligence"])
    authorize = build_household_authorizer(household_tokens)

    @router.post("/observations/{observation_id}/confirm")
    def confirm(
        household_id: str,
        observation_id: str,
        request: ObservationReviewRequest,
        _: None = Depends(authorize),
    ):
        observation = confirm_observation(
            household_id,
            observation_id,
            request.confirmed_value,
            observation_storage,
        )
        if observation is None:
            raise HTTPException(status_code=404, detail="Observation not found")
        return observation.model_dump(mode="json")

    @router.post("/intelligence/refresh")
    def refresh(household_id: str, _: None = Depends(authorize)):
        report = refresh_household_intelligence(
            household_id,
            observation_storage,
            task_storage,
        )
        return report.model_dump(mode="json")

    return router

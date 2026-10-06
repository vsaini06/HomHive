from enum import Enum

from pydantic import BaseModel, Field

from .observation import ObservationCategory


class InterventionStatus(str, Enum):
    NONE = "none"
    MONITOR = "monitor"
    PLAN = "plan"
    ACT_NOW = "act_now"


class InterventionDecision(BaseModel):
    location: str
    category: ObservationCategory
    status: InterventionStatus
    hours_to_threshold: float | None = Field(
        default=None,
        ge=0.0,
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    reason: str
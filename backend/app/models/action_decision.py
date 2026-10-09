from enum import Enum

from pydantic import BaseModel, Field

from .observation import ConditionType


class ActionState(str, Enum):
    """What HomHive currently wants to do about a predicted condition."""

    NONE = "none"
    MONITOR = "monitor"
    PLAN = "plan"
    ACT_NOW = "act_now"


class ActionDecision(BaseModel):
    """HomHive's decision about whether a predicted condition needs action."""

    location: str
    category: ConditionType
    status: ActionState

    hours_to_threshold: float | None = Field(
        default=None,
        ge=0.0,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str
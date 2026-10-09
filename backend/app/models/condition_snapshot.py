from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from .observation import (
    ConditionType,
    Observation,
)


class ConditionTrend(str, Enum):
    """The recent direction of a tracked household condition."""
    RISING = "rising"
    STABLE = "stable"
    FALLING = "falling"
    UNKNOWN = "unknown"


class ConditionSnapshot(BaseModel):
    """HomHive's current derived view of one household condition."""
    location: str
    category: ConditionType
    current_value: float = Field(
        ge=0.0,
        le=1.0,
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    trend: ConditionTrend = (
        ConditionTrend.UNKNOWN
    )
    latest_observation: Observation
    observation_count: int = Field(
        ge=1,
    )
    updated_at: datetime

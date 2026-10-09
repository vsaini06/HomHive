from datetime import datetime

from pydantic import BaseModel, Field

from .observation import ConditionType


class ThresholdCrossing(BaseModel):
    """When a tracked condition is expected to reach an actionable level."""

    location: str
    category: ConditionType

    current_value: float = Field(
        ge=0.0,
        le=1.0,
    )

    threshold: float = Field(
        ge=0.0,
        le=1.0,
    )

    rate_per_hour: float

    hours_to_threshold: float = Field(
        ge=0.0,
    )

    predicted_crossing_at: datetime

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
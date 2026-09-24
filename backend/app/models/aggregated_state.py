from datetime import datetime

from pydantic import BaseModel, Field
from .observation import Observation

from .enums import (
    ObservationCategory,
    TrendDirection,
)


class AggregatedState(BaseModel):
    location: str
    category: ObservationCategory
    current_value: float = Field(
        ge=0.0,
        le=1.0,
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    trend: TrendDirection = TrendDirection.UNKNOWN
    latest_observation: Observation
    observation_count: int = Field(
        ge=1,
    )
    updated_at: datetime
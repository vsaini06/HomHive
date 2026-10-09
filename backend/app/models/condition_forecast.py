from datetime import datetime

from pydantic import BaseModel, Field

from .condition_snapshot import ConditionTrend
from .observation import ConditionType


class ConditionForecast(BaseModel):
    """A projected future level for one household condition."""

    location: str
    category: ConditionType

    current_value: float = Field(
        ge=0.0,
        le=1.0,
    )

    predicted_value: float = Field(
        ge=0.0,
        le=1.0,
    )

    rate_per_hour: float

    forecast_hours: float = Field(
        gt=0.0,
    )

    predicted_at: datetime

    trend: ConditionTrend

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

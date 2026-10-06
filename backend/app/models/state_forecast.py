from datetime import datetime

from pydantic import BaseModel, Field

from .observation import ObservationCategory
from .aggregated_state import TrendDirection


class StateForecast(BaseModel):
    location: str
    category: ObservationCategory

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
    trend: TrendDirection
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
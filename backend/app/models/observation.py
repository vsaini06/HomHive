from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .enums import ObservationCategory, ObservationSource


class Observation(BaseModel):
    id: str
    source: ObservationSource
    location: str
    entity_id: str | None = None
    category: ObservationCategory
    value: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def state_key(self) -> str:
        if self.entity_id is not None:
            return (
                f"{self.entity_id}:"
                f"{self.category.value}"
            )

        return (
            f"{self.location}:"
            f"{self.category.value}"
        )
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ObservationSource(str, Enum):
    """Where this household observation came from."""
    PHOTO = "photo"
    VIDEO = "video"
    USER_INPUT = "user_input"
    HISTORY = "history"
    EXTERNAL_RESEARCH = "external_research"


class ConditionType(str, Enum):
    """Household conditions HomHive currently knows how to track."""
    DISH_LOAD = "dish_load"
    LAUNDRY_LOAD = "laundry_load"
    PLANT_CONDITION = "plant_condition"
    LAWN_CONDITION = "lawn_condition"
    MAINTENANCE_STATUS = "maintenance_status"


class Observation(BaseModel):
    """Household condition"""
    id: str
    source: ObservationSource
    location: str
    entity_id: str | None = None
    category: ConditionType
    value: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    def state_key(self) -> str:
        """Return the key used to keep this condition's history together."""
        # Once we know the physical object, its ID is more precise than its room.
        if self.entity_id is not None:
            return (
                f"{self.entity_id}:"
                f"{self.category.value}"
            )

        # Location is the fallback when this condition is not tied to a known entity.
        return (
            f"{self.location}:"
            f"{self.category.value}"
        )

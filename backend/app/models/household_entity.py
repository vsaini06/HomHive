from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .enums import EntityType


class HouseholdEntity(BaseModel):
    id: str
    entity_type: EntityType
    name: str = Field(min_length=1)
    location: str = Field(min_length=1)

    identity: str | None = None

    identification_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    attributes: dict[str, Any] = Field(
        default_factory=dict
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )
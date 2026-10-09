from typing import Any

from pydantic import BaseModel, Field

from .enums import EntityType


class EntityCandidate(BaseModel):
    """A tentative identity for something HomHive has just recognized."""

    entity_type: EntityType
    identity: str | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    attributes: dict[str, Any] = Field(
        default_factory=dict
    )

    evidence: list[str] = Field(
        default_factory=list
    )
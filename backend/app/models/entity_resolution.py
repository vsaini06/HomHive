from pydantic import BaseModel, Field

from .enums import EntityResolutionStatus


class EntityResolutionResult(BaseModel):
    status: EntityResolutionStatus

    matched_entity_id: str | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reasons: list[str] = Field(
        default_factory=list
    )
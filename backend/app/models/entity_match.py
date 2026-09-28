from pydantic import BaseModel, Field


class EntityMatchEvidence(BaseModel):
    entity_id: str

    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    reasons: list[str] = Field(
        default_factory=list
    )
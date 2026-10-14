from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ResearchPurpose(str, Enum):
    PLANT_CARE = "plant_care"
    APPLIANCE_GUIDANCE = "appliance_guidance"
    MAINTENANCE = "maintenance"
    HOUSEHOLD_CONTEXT = "household_context"


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=500)
    purpose: ResearchPurpose
    max_results: int = Field(default=5, ge=1, le=5)


class ResearchEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl
    content: str = Field(min_length=1, max_length=5000)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    published_date: str | None = None


class ResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    purpose: ResearchPurpose
    evidence: list[ResearchEvidence]
    provider: str = "tavily"
    request_id: str | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

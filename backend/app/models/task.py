from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .enums import TaskStatus, UrgencyLevel


class Task(BaseModel):
    id: str
    description: str = Field(min_length=1)
    source_observation_id: str
    urgency: UrgencyLevel
    estimated_effort_minutes: int = Field(gt=0)
    deadline: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Where a household task is in its lifecycle."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class TaskUrgency(str, Enum):
    """How quickly a household task currently needs attention."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Task(BaseModel):
    """A piece of household work HomHive has decided should exist."""
    id: str
    task_key: str
    description: str = Field(
        min_length=1
    )
    source_observation_id: str | None = None
    urgency: TaskUrgency
    estimated_effort_minutes: int = Field(
        gt=0
    )
    deadline: datetime | None = None
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

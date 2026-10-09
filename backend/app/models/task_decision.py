from enum import Enum

from pydantic import BaseModel

from .task import Task


class TaskDecisionReason(str, Enum):
    """Why HomHive did or did not create a task from an observation."""

    TASK_CREATED = "task_created"
    UNSUPPORTED_CONDITION = "unsupported_category"
    BELOW_TRIGGER_LEVEL = "below_threshold"
    LOW_CONFIDENCE = "low_confidence"
    ACTIVE_TASK_ALREADY_EXISTS = "duplicate_active_task"


class TaskDecision(BaseModel):
    """The outcome of deciding whether an observation should create work."""

    task: Task | None
    reason: TaskDecisionReason

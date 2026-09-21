from enum import Enum

from pydantic import BaseModel

from .task import Task


class TaskDiscoveryReason(str, Enum):
    TASK_CREATED = "task_created"
    UNSUPPORTED_CATEGORY = "unsupported_category"
    BELOW_THRESHOLD = "below_threshold"
    LOW_CONFIDENCE = "low_confidence"
    DUPLICATE_ACTIVE_TASK = "duplicate_active_task"


class TaskDiscoveryResult(BaseModel):
    task: Task | None
    reason: TaskDiscoveryReason
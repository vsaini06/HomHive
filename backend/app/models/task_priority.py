from pydantic import BaseModel, Field

from .task import Task


class PrioritizedTask(BaseModel):
    task: Task

    priority_score: float = Field(
        ge=0.0,
        le=1.0,
    )
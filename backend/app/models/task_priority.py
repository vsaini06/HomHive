from pydantic import BaseModel, Field

from .task import Task


class ScoredTask(BaseModel):
    """A task paired with its current planning score."""

    task: Task

    priority_score: float = Field(
        ge=0.0,
        le=1.0,
    )

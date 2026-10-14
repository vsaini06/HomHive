from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class NoiseLevel(str, Enum):
    QUIET = "quiet"
    NORMAL = "normal"
    NOISY = "noisy"


class PlanningContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_minutes: int = Field(gt=0, le=720)
    at_home: bool = True
    quiet_hours_active: bool = False
    max_tasks: int = Field(default=5, ge=1, le=20)


class TaskExecutionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    active_minutes: int = Field(gt=0)
    passive_minutes: int = Field(default=0, ge=0)
    noise_level: NoiseLevel = NoiseLevel.NORMAL
    requires_home: bool = True


class TaskFeasibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    feasible: bool
    reason: str
    active_minutes: int = Field(gt=0)
    passive_minutes: int = Field(ge=0)


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    order: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)
    active_minutes: int = Field(gt=0)
    passive_minutes: int = Field(ge=0)


class DeferredTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    reason: str = Field(min_length=1, max_length=500)


class HouseholdPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1000)
    steps: list[PlanStep]
    deferred: list[DeferredTask]
    planner: str

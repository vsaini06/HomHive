from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from .action_decision import ActionDecision
from .condition_forecast import ConditionForecast
from .condition_snapshot import ConditionSnapshot
from .household_state import HouseholdState
from .task import Task
from .task_priority import ScoredTask


class HouseholdIntelligence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    household_id: str = Field(min_length=1)
    state: HouseholdState
    snapshots: list[ConditionSnapshot]
    forecasts: list[ConditionForecast]
    action_decisions: list[ActionDecision]
    tasks: list[Task]
    ranked_tasks: list[ScoredTask]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

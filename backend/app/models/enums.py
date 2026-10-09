from enum import Enum

from .condition_snapshot import (
    ConditionTrend,
)
from .observation import (
    ConditionType,
    ObservationSource,
)
from .task import (
    TaskStatus,
    TaskUrgency,
)


class EntityType(str, Enum):
    PLANT = "plant"
    APPLIANCE = "appliance"
    AREA = "area"
    FIXTURE = "fixture"
    OTHER = "other"


class EntityResolutionStatus(str, Enum):
    MATCH = "match"
    CREATE = "create"
    UNCERTAIN = "uncertain"


__all__ = [
    "ConditionType",
    "ObservationSource",
    "TaskStatus",
    "TaskUrgency",
    "ConditionTrend",
    "EntityType",
    "EntityResolutionStatus",
]

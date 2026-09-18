from enum import Enum


class ObservationSource(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"
    USER_INPUT = "user_input"
    HISTORY = "history"
    EXTERNAL_RESEARCH = "external_research"


class ObservationCategory(str, Enum):
    DISH_LOAD = "dish_load"
    LAUNDRY_LOAD = "laundry_load"
    PLANT_CONDITION = "plant_condition"
    LAWN_CONDITION = "lawn_condition"
    MAINTENANCE_STATUS = "maintenance_status"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISMISSED = "dismissed"

class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
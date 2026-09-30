import strawberry
from enum import Enum

@strawberry.enum
class EntityTypeEnum(Enum):
    PLANT = "plant"
    APPLIANCE = "appliance"

@strawberry.type
class HouseholdEntityType:
    id: str
    name: str
    location: str
    identity: str | None
    entity_type: EntityTypeEnum
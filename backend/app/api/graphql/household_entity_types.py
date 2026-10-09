from enum import Enum

import strawberry


@strawberry.enum(name="EntityTypeEnum")
class HouseholdEntityKind(Enum):
    """Entity kinds currently exposed through the household GraphQL API."""

    PLANT = "plant"
    APPLIANCE = "appliance"
    AREA = "area"
    FIXTURE = "fixture"
    OTHER = "other"


@strawberry.type(name="HouseholdEntityType")
class HouseholdEntityView:
    """The household-entity fields clients can request through GraphQL."""

    id: str
    name: str
    location: str
    identity: str | None
    entity_type: HouseholdEntityKind
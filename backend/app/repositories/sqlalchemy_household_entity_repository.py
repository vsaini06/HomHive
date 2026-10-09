"""SQL-backed household entity storage with transaction-scoped sessions."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.household_entity_mapping import to_entity_record, to_household_entity
from app.db.household_entity_record import HouseholdEntityRecord
from app.models import EntityType, HouseholdEntity


class SQLAlchemyHouseholdEntityRepository:
    """Persist household entities while exposing only validated domain models."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_entity(self, entity: HouseholdEntity) -> HouseholdEntity:
        """Insert an entity and commit; duplicate IDs propagate integrity errors."""
        with self._session_factory.begin() as session:
            record = to_entity_record(entity)
            session.add(record)
            session.flush()
            result = to_household_entity(record)
        return result

    def find_by_id(self, entity_id: str) -> HouseholdEntity | None:
        with self._session_factory() as session:
            record = session.get(HouseholdEntityRecord, entity_id)
            return to_household_entity(record) if record is not None else None

    def list_entities(
        self,
        location: str | None = None,
        entity_type: EntityType | None = None,
    ) -> list[HouseholdEntity]:
        statement = select(HouseholdEntityRecord)
        if location is not None:
            statement = statement.where(HouseholdEntityRecord.location == location)
        if entity_type is not None:
            statement = statement.where(HouseholdEntityRecord.entity_type == entity_type.value)
        statement = statement.order_by(HouseholdEntityRecord.id)
        with self._session_factory() as session:
            return [to_household_entity(row) for row in session.scalars(statement).all()]

    def rename_entity(self, entity_id: str, new_name: str) -> HouseholdEntity | None:
        """Commit a rename, or return None when the entity is absent."""
        with self._session_factory.begin() as session:
            record = session.get(HouseholdEntityRecord, entity_id)
            if record is None:
                return None
            record.name = new_name
            from datetime import datetime, timezone
            record.updated_at = datetime.now(timezone.utc)
            session.flush()
            result = to_household_entity(record)
        return result

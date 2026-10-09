from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.observation_mapping import to_observation, to_observation_record
from app.db.observation_record import ObservationRecord
from app.models import Observation


class SQLAlchemyObservationRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add_observation(self, household_id: str, observation: Observation) -> Observation:
        if not household_id:
            raise ValueError("household_id must not be empty")
        try:
            with self._session_factory.begin() as session:
                record = to_observation_record(household_id, observation)
                session.add(record)
                session.flush()
                result = to_observation(record)
        except IntegrityError as exc:
            raise ValueError(f"Observation already exists: {observation.id}") from exc
        return result

    def find_observation(self, household_id: str, observation_id: str) -> Observation | None:
        with self._session_factory() as session:
            record = session.get(ObservationRecord, (household_id, observation_id))
            return to_observation(record) if record is not None else None

    def list_observations(self, household_id: str) -> list[Observation]:
        statement = (
            select(ObservationRecord)
            .where(ObservationRecord.household_id == household_id)
            .order_by(ObservationRecord.timestamp, ObservationRecord.id)
        )
        with self._session_factory() as session:
            return [to_observation(record) for record in session.scalars(statement).all()]

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.task_mapping import to_task, to_task_record
from app.db.task_record import TaskRecord
from app.models import Task


class SQLAlchemyTaskRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add_task(self, household_id: str, task: Task) -> Task:
        if not household_id:
            raise ValueError("household_id must not be empty")
        try:
            with self._session_factory.begin() as session:
                record = to_task_record(household_id, task)
                session.add(record)
                session.flush()
                result = to_task(record)
        except IntegrityError as exc:
            raise ValueError(f"Task already exists: {task.id}") from exc
        return result

    def find_task(self, household_id: str, task_id: str) -> Task | None:
        with self._session_factory() as session:
            record = session.get(TaskRecord, (household_id, task_id))
            return to_task(record) if record is not None else None

    def list_tasks(self, household_id: str) -> list[Task]:
        statement = (
            select(TaskRecord)
            .where(TaskRecord.household_id == household_id)
            .order_by(TaskRecord.created_at, TaskRecord.id)
        )
        with self._session_factory() as session:
            return [to_task(record) for record in session.scalars(statement).all()]

    def save_task(self, household_id: str, task: Task) -> Task:
        if not household_id:
            raise ValueError("household_id must not be empty")
        with self._session_factory.begin() as session:
            record = session.get(TaskRecord, (household_id, task.id))
            if record is None:
                raise ValueError(f"Task does not exist: {task.id}")
            updated = to_task_record(household_id, task)
            for field in (
                "task_key", "description", "source_observation_id", "urgency",
                "estimated_effort_minutes", "deadline", "confidence", "status",
                "created_at", "task_metadata",
            ):
                setattr(record, field, getattr(updated, field))
            session.flush()
            result = to_task(record)
        return result

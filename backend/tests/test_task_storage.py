from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.task_record import TaskRecord
from app.models import Task, TaskStatus, TaskUrgency
from app.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.repositories.sqlalchemy_task_repository import SQLAlchemyTaskRepository
from app.repositories.task_storage import TaskStorage


def make_task(task_id="task_1", *, status=TaskStatus.PENDING):
    return Task(
        id=task_id,
        task_key="predictive:kitchen:dish_load",
        description="Wash dishes",
        urgency=TaskUrgency.MEDIUM,
        estimated_effort_minutes=15,
        confidence=0.85,
        status=status,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata={"reasons": ["forecast"]},
    )


@pytest.fixture(params=["memory", "sql"])
def storage(request, tmp_path):
    if request.param == "memory":
        yield lambda: InMemoryTaskRepository()
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'tasks.sqlite'}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        yield lambda: SQLAlchemyTaskRepository(factory)
        engine.dispose()


def test_repository_matches_storage_contract(storage):
    assert isinstance(storage(), TaskStorage)


def test_tasks_can_be_retrieved_after_writes(storage):
    repository = storage()
    saved = repository.add_task("home_a", make_task())
    assert saved.id == "task_1"
    assert repository.find_task("home_a", "task_1") == make_task()


def test_tasks_remain_isolated_by_household(storage):
    repository = storage()
    repository.add_task("home_a", make_task())
    repository.add_task("home_b", make_task(status=TaskStatus.COMPLETED))
    assert repository.find_task("home_a", "task_1").status == TaskStatus.PENDING
    assert repository.find_task("home_b", "task_1").status == TaskStatus.COMPLETED
    assert repository.find_task("other", "task_1") is None


def test_duplicate_ids_are_rejected_without_overwriting(storage):
    repository = storage()
    repository.add_task("home", make_task())
    with pytest.raises(ValueError, match="already exists"):
        repository.add_task("home", make_task(status=TaskStatus.DISMISSED))
    assert repository.find_task("home", "task_1").status == TaskStatus.PENDING


def test_status_and_metadata_updates_are_persisted(storage):
    repository = storage()
    repository.add_task("home", make_task())
    task = repository.find_task("home", "task_1")
    task.status = TaskStatus.DISMISSED
    task.metadata["reasons"].append("low_confidence")
    repository.save_task("home", task)
    current = repository.find_task("home", "task_1")
    assert current.status == TaskStatus.DISMISSED
    assert current.metadata == {"reasons": ["forecast", "low_confidence"]}


def test_missing_task_cannot_be_updated(storage):
    with pytest.raises(ValueError, match="does not exist"):
        storage().save_task("home", make_task())


def test_stored_metadata_does_not_alias_caller_data(storage):
    repository = storage()
    original = make_task()
    repository.add_task("home", original)
    original.metadata["reasons"].append("outside")
    retrieved = repository.find_task("home", "task_1")
    retrieved.metadata["reasons"].append("elsewhere")
    assert repository.find_task("home", "task_1").metadata == {"reasons": ["forecast"]}


def test_tasks_are_returned_in_creation_order(storage):
    repository = storage()
    repository.add_task("home", make_task("z"))
    repository.add_task("home", make_task("a"))
    assert [task.id for task in repository.list_tasks("home")] == ["a", "z"]
    assert repository.list_tasks("elsewhere") == []


def test_household_id_required_for_writes(storage):
    with pytest.raises(ValueError, match="household_id"):
        storage().add_task("", make_task())


def test_sql_repository_survives_independent_instances(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'durable_tasks.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    SQLAlchemyTaskRepository(factory).add_task("home", make_task())
    second = SQLAlchemyTaskRepository(factory)
    task = second.find_task("home", "task_1")
    task.status = TaskStatus.IN_PROGRESS
    second.save_task("home", task)
    assert SQLAlchemyTaskRepository(factory).find_task("home", "task_1").status == TaskStatus.IN_PROGRESS
    engine.dispose()


def test_task_table_registered():
    assert TaskRecord.__table__ is Base.metadata.tables["tasks"]

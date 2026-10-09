from copy import deepcopy
from datetime import timezone

from app.models import Task, TaskStatus, TaskUrgency

from .task_record import TaskRecord


def to_task_record(household_id: str, task: Task) -> TaskRecord:
    return TaskRecord(
        household_id=household_id,
        id=task.id,
        task_key=task.task_key,
        description=task.description,
        source_observation_id=task.source_observation_id,
        urgency=task.urgency.value,
        estimated_effort_minutes=task.estimated_effort_minutes,
        deadline=task.deadline,
        confidence=task.confidence,
        status=task.status.value,
        created_at=task.created_at,
        task_metadata=deepcopy(task.metadata),
    )


def to_task(record: TaskRecord) -> Task:
    deadline = record.deadline
    if deadline is not None and deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    created_at = record.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return Task(
        id=record.id,
        task_key=record.task_key,
        description=record.description,
        source_observation_id=record.source_observation_id,
        urgency=TaskUrgency(record.urgency),
        estimated_effort_minutes=record.estimated_effort_minutes,
        deadline=deadline,
        confidence=record.confidence,
        status=TaskStatus(record.status),
        created_at=created_at,
        metadata=deepcopy(record.task_metadata),
    )

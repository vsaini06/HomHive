from typing import Protocol, runtime_checkable

from app.models import Task


@runtime_checkable
class TaskStorage(Protocol):
    def add_task(self, household_id: str, task: Task) -> Task: ...

    def find_task(self, household_id: str, task_id: str) -> Task | None: ...

    def list_tasks(self, household_id: str) -> list[Task]: ...

    def save_task(self, household_id: str, task: Task) -> Task: ...

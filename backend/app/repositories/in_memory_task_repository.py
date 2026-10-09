from app.models import Task


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Task]] = {}

    def add_task(self, household_id: str, task: Task) -> Task:
        if not household_id:
            raise ValueError("household_id must not be empty")
        tasks = self._tasks.setdefault(household_id, {})
        if task.id in tasks:
            raise ValueError(f"Task already exists: {task.id}")
        tasks[task.id] = task.model_copy(deep=True)
        return tasks[task.id].model_copy(deep=True)

    def find_task(self, household_id: str, task_id: str) -> Task | None:
        task = self._tasks.get(household_id, {}).get(task_id)
        return task.model_copy(deep=True) if task is not None else None

    def list_tasks(self, household_id: str) -> list[Task]:
        tasks = self._tasks.get(household_id, {}).values()
        return [task.model_copy(deep=True) for task in sorted(tasks, key=lambda item: (item.created_at, item.id))]

    def save_task(self, household_id: str, task: Task) -> Task:
        if not household_id:
            raise ValueError("household_id must not be empty")
        tasks = self._tasks.get(household_id, {})
        if task.id not in tasks:
            raise ValueError(f"Task does not exist: {task.id}")
        tasks[task.id] = task.model_copy(deep=True)
        return tasks[task.id].model_copy(deep=True)

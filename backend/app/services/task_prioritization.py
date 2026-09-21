from app.models import (
    PrioritizedTask,
    Task,
    UrgencyLevel,
)


URGENCY_SCORES = {
    UrgencyLevel.LOW: 0.25,
    UrgencyLevel.MEDIUM: 0.50,
    UrgencyLevel.HIGH: 0.75,
    UrgencyLevel.CRITICAL: 1.00,
}


def calculate_effort_score(
    effort_minutes: int,
) -> float:
    return 1 / (1 + effort_minutes / 30)


def calculate_priority_score(
    task: Task,
) -> float:
    urgency_score = URGENCY_SCORES[task.urgency]

    effort_score = calculate_effort_score(
        task.estimated_effort_minutes
    )

    priority_score = (
        urgency_score * 0.60
        + task.confidence * 0.30
        + effort_score * 0.10
    )

    return round(priority_score, 4)


def prioritize_task(
    task: Task,
) -> PrioritizedTask:
    return PrioritizedTask(
        task=task,
        priority_score=calculate_priority_score(task),
    )

def prioritize_tasks(
    tasks: list[Task],
) -> list[PrioritizedTask]:
    prioritized_tasks = [
        prioritize_task(task)
        for task in tasks
    ]

    return sorted(
        prioritized_tasks,
        key=lambda item: (
            -item.priority_score,
            item.task.id,
        ),
    )
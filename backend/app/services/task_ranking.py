from app.models import (
    ScoredTask,
    Task,
    TaskUrgency,
)


# Urgency carries most of the score because time-sensitive work
# should generally outrank convenience.
URGENCY_WEIGHT = 0.60

# Confidence matters, but uncertain evidence should not overpower urgency.
CONFIDENCE_WEIGHT = 0.30

# Shorter tasks get a small advantage when everything else is similar.
EFFORT_WEIGHT = 0.10


URGENCY_SCORES = {
    TaskUrgency.LOW: 0.25,
    TaskUrgency.MEDIUM: 0.50,
    TaskUrgency.HIGH: 0.75,
    TaskUrgency.CRITICAL: 1.00,
}


def _effort_score(
    effort_minutes: int,
) -> float:
    """Give shorter tasks a modest planning advantage."""

    return 1 / (
        1 + effort_minutes / 30
    )


def _priority_score(
    task: Task,
) -> float:
    """Calculate the planning score used to compare one task with another."""

    urgency_score = (
        URGENCY_SCORES[task.urgency]
    )

    effort_score = _effort_score(
        task.estimated_effort_minutes
    )

    score = (
        urgency_score * URGENCY_WEIGHT
        + task.confidence * CONFIDENCE_WEIGHT
        + effort_score * EFFORT_WEIGHT
    )

    return round(
        score,
        4,
    )


def score_task(
    task: Task,
) -> ScoredTask:
    """Pair a task with the score HomHive currently gives it."""

    return ScoredTask(
        task=task,
        priority_score=_priority_score(task),
    )


def rank_tasks(
    tasks: list[Task],
) -> list[ScoredTask]:
    """Rank household tasks from highest planning priority to lowest."""

    scored_tasks = [
        score_task(task)
        for task in tasks
    ]

    # Task ID gives us a stable order when two tasks receive the same score.
    return sorted(
        scored_tasks,
        key=lambda scored_task: (
            -scored_task.priority_score,
            scored_task.task.id,
        ),
    )
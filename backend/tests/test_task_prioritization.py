from app.models import Task
from app.services.task_prioritization import (
    calculate_effort_score,
    calculate_priority_score,
    prioritize_task,
    prioritize_tasks,
)

#-tests-

#-1-
def make_task(
    task_id: str = "task_001",
    urgency: str = "medium",
    confidence: float = 0.90,
    effort_minutes: int = 30,
) -> Task:
    return Task(
        id=task_id,
        task_key=f"test:{task_id}",
        description="Test task",
        source_observation_id="obs_001",
        urgency=urgency,
        estimated_effort_minutes=effort_minutes,
        confidence=confidence,
    )

#-2-
def test_effort_score_for_30_minutes_is_half():
    score = calculate_effort_score(30)

    assert score == 0.5

#-3-
def test_shorter_task_has_higher_effort_score():
    short_score = calculate_effort_score(15)
    long_score = calculate_effort_score(60)

    assert short_score > long_score

#-4-
def test_priority_score_stays_between_zero_and_one():
    task = make_task(
        urgency="high",
        confidence=0.90,
        effort_minutes=15,
    )

    score = calculate_priority_score(task)

    assert 0.0 <= score <= 1.0

#-5-
def test_higher_urgency_produces_higher_priority():
    medium_task = make_task(
        task_id="task_medium",
        urgency="medium",
        confidence=0.90,
        effort_minutes=30,
    )
    high_task = make_task(
        task_id="task_high",
        urgency="high",
        confidence=0.90,
        effort_minutes=30,
    )

    medium_score = calculate_priority_score(medium_task)
    high_score = calculate_priority_score(high_task)

    assert high_score > medium_score

#-6-
def test_higher_confidence_produces_higher_priority():
    lower_confidence_task = make_task(
        task_id="task_lower_confidence",
        confidence=0.75,
    )

    higher_confidence_task = make_task(
        task_id="task_higher_confidence",
        confidence=0.95,
    )

    lower_score = calculate_priority_score(
        lower_confidence_task
    )
    higher_score = calculate_priority_score(
        higher_confidence_task
    )

    assert higher_score > lower_score

#-7-
def test_prioritize_task_returns_task_and_score():
    task = make_task()

    result = prioritize_task(task)

    assert result.task == task
    assert result.priority_score == calculate_priority_score(task)

#-8-
def test_urgency_outweighs_effort_when_confidence_is_equal():
    high_urgency_long_task = make_task(
        task_id="task_high_long",
        urgency="high",
        confidence=0.90,
        effort_minutes=60,
    )

    medium_urgency_short_task = make_task(
        task_id="task_medium_short",
        urgency="medium",
        confidence=0.90,
        effort_minutes=5,
    )

    high_score = calculate_priority_score(
        high_urgency_long_task
    )
    medium_score = calculate_priority_score(
        medium_urgency_short_task
    )

    assert high_score > medium_score

#-9-
def test_prioritize_tasks_orders_highest_score_first():
    low_task = make_task(
        task_id="task_low",
        urgency="low",
        confidence=0.90,
        effort_minutes=30,
    )
    medium_task = make_task(
        task_id="task_medium",
        urgency="medium",
        confidence=0.90,
        effort_minutes=30,
    )
    high_task = make_task(
        task_id="task_high",
        urgency="high",
        confidence=0.90,
        effort_minutes=30,
    )

    prioritized = prioritize_tasks(
        [medium_task, low_task, high_task]
    )

    assert prioritized[0].task.id == "task_high"
    assert prioritized[1].task.id == "task_medium"
    assert prioritized[2].task.id == "task_low"

#-10-
def test_prioritize_tasks_returns_empty_list_for_no_tasks():
    prioritized = prioritize_tasks([])

    assert prioritized == []

#-11-
def test_equal_priority_uses_task_id_as_tiebreaker():
    task_b = make_task(
        task_id="task_b",
        urgency="medium",
        confidence=0.90,
        effort_minutes=30,
    )
    task_a = make_task(
        task_id="task_a",
        urgency="medium",
        confidence=0.90,
        effort_minutes=30,
    )

    prioritized = prioritize_tasks(
        [task_b, task_a]
    )

    assert prioritized[0].task.id == "task_a"
    assert prioritized[1].task.id == "task_b"
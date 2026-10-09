import pytest

from app.models import Task
from app.services.task_ranking import (
    rank_tasks,
    score_task,
)


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


def test_medium_task_with_30_minute_effort_has_expected_score():
    task = make_task(
        urgency="medium",
        confidence=0.90,
        effort_minutes=30,
    )

    scored = score_task(task)

    assert scored.priority_score == pytest.approx(0.62)


def test_shorter_task_scores_higher_when_other_signals_match():
    short_task = make_task(
        task_id="task_short",
        effort_minutes=15,
    )
    long_task = make_task(
        task_id="task_long",
        effort_minutes=60,
    )

    short_score = score_task(short_task).priority_score
    long_score = score_task(long_task).priority_score

    assert short_score > long_score


def test_priority_score_stays_between_zero_and_one():
    task = make_task(
        urgency="high",
        confidence=0.90,
        effort_minutes=15,
    )

    scored = score_task(task)

    assert 0.0 <= scored.priority_score <= 1.0


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

    medium_score = score_task(
        medium_task
    ).priority_score
    high_score = score_task(
        high_task
    ).priority_score

    assert high_score > medium_score


def test_higher_confidence_produces_higher_priority():
    lower_confidence_task = make_task(
        task_id="task_lower_confidence",
        confidence=0.75,
    )
    higher_confidence_task = make_task(
        task_id="task_higher_confidence",
        confidence=0.95,
    )

    lower_score = score_task(
        lower_confidence_task
    ).priority_score
    higher_score = score_task(
        higher_confidence_task
    ).priority_score

    assert higher_score > lower_score


def test_score_task_returns_task_and_score():
    task = make_task()

    scored = score_task(task)

    assert scored.task == task
    assert 0.0 <= scored.priority_score <= 1.0


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

    high_score = score_task(
        high_urgency_long_task
    ).priority_score
    medium_score = score_task(
        medium_urgency_short_task
    ).priority_score

    assert high_score > medium_score


def test_rank_tasks_orders_highest_score_first():
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

    ranked = rank_tasks(
        [medium_task, low_task, high_task]
    )

    assert ranked[0].task.id == "task_high"
    assert ranked[1].task.id == "task_medium"
    assert ranked[2].task.id == "task_low"


def test_rank_tasks_returns_empty_list_for_no_tasks():
    ranked = rank_tasks([])

    assert ranked == []


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

    ranked = rank_tasks(
        [task_b, task_a]
    )

    assert ranked[0].task.id == "task_a"
    assert ranked[1].task.id == "task_b"

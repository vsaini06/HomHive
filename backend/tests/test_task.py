import pytest
from pydantic import ValidationError

from app.models import Task

#-tests-

#-1-
def test_valid_task():
    task = Task(
        id="task_001",
        task_key="kitchen:dish_load",
        description="Clear the kitchen dishes",
        source_observation_id="obs_001",
        urgency="high",
        estimated_effort_minutes=15,
        confidence=0.91,
    )

    assert task.id == "task_001"
    assert task.description == "Clear the kitchen dishes"
    assert task.source_observation_id == "obs_001"
    assert task.urgency.value == "high"
    assert task.estimated_effort_minutes == 15
    assert task.confidence == 0.91
    assert task.status.value == "pending"
    assert task.deadline is None

#-2-
def test_task_rejects_invalid_urgency():
    with pytest.raises(ValidationError):
        Task(
            id="task_002",
            task_key="kitchen:dish_load",
            description="Clear the kitchen dishes",
            source_observation_id="obs_001",
            urgency="super_urgent",
            estimated_effort_minutes=15,
            confidence=0.91,
        )

#-3-
def test_task_rejects_zero_effort():
    with pytest.raises(ValidationError):
        Task(
            id="task_003",
            task_key="kitchen:dish_load",
            description="Clear the kitchen dishes",
            source_observation_id="obs_001",
            urgency="high",
            estimated_effort_minutes=0,
            confidence=0.91,
        )

#-4-
def test_task_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        Task(
            id="task_004",
            task_key="kitchen:dish_load",
            description="Clear the kitchen dishes",
            source_observation_id="obs_001",
            urgency="high",
            estimated_effort_minutes=15,
            confidence=1.5,
        )

#-5-
def test_task_rejects_empty_description():
    with pytest.raises(ValidationError):
        Task(
            id="task_005",
            task_key="kitchen:dish_load",
            description="",
            source_observation_id="obs_001",
            urgency="high",
            estimated_effort_minutes=15,
            confidence=0.91,
        )
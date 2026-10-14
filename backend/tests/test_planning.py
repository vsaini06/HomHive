import json
from types import SimpleNamespace

from app.models import ScoredTask, Task, TaskUrgency
from app.planning import (
    NebiusPlanningProvider,
    NoiseLevel,
    PlanningContext,
    TaskExecutionProfile,
    build_deterministic_plan,
    evaluate_task_feasibility,
    execution_profile_for_task,
)


def task(identifier, key="kitchen:dish_load", minutes=15):
    return Task(
        id=identifier,
        task_key=key,
        description=f"Task {identifier}",
        urgency=TaskUrgency.MEDIUM,
        estimated_effort_minutes=minutes,
        confidence=0.9,
    )


def test_laundry_profile_separates_active_and_passive_time():
    profile = execution_profile_for_task(task("laundry", "laundry:laundry_load", 45))
    assert profile.active_minutes == 5
    assert profile.passive_minutes == 40


def test_noisy_task_is_blocked_during_quiet_hours():
    assessment = evaluate_task_feasibility(
        TaskExecutionProfile(
            task_id="vacuum",
            active_minutes=20,
            noise_level=NoiseLevel.NOISY,
        ),
        PlanningContext(available_minutes=30, quiet_hours_active=True),
    )
    assert not assessment.feasible
    assert assessment.reason == "blocked by quiet hours"


def test_task_requiring_home_is_blocked_when_away():
    assessment = evaluate_task_feasibility(
        TaskExecutionProfile(task_id="dishes", active_minutes=15, requires_home=True),
        PlanningContext(available_minutes=30, at_home=False),
    )
    assert not assessment.feasible


def test_deterministic_plan_fits_tasks_into_active_window():
    ranked = [
        ScoredTask(task=task("one", minutes=15), priority_score=0.8),
        ScoredTask(task=task("two", minutes=20), priority_score=0.7),
    ]
    plan, _ = build_deterministic_plan(ranked, PlanningContext(available_minutes=20))
    assert [step.task_id for step in plan.steps] == ["one"]
    assert plan.deferred[0].task_id == "two"


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def test_nemotron_provider_rejects_unknown_task_ids():
    content = json.dumps({
        "summary": "Plan",
        "steps": [
            {
                "task_id": "invented",
                "order": 1,
                "reason": "do it",
                "active_minutes": 5,
                "passive_minutes": 0,
            }
        ],
        "deferred": [],
    })
    provider = NebiusPlanningProvider(client=FakeClient(content), model="nvidia/example-nemotron")
    ranked = [ScoredTask(task=task("known"), priority_score=0.8)]
    feasibility = [
        evaluate_task_feasibility(
            TaskExecutionProfile(task_id="known", active_minutes=15),
            PlanningContext(available_minutes=30),
        )
    ]

    try:
        provider.plan(ranked, PlanningContext(available_minutes=30), feasibility, [])
        assert False, "expected validation failure"
    except ValueError as exc:
        assert "unknown task" in str(exc)


def test_nemotron_provider_accepts_valid_structured_plan():
    content = json.dumps({
        "summary": "Start with dishes.",
        "steps": [
            {
                "task_id": "known",
                "order": 1,
                "reason": "highest feasible priority",
                "active_minutes": 15,
                "passive_minutes": 0,
            }
        ],
        "deferred": [],
    })
    client = FakeClient(content)
    provider = NebiusPlanningProvider(client=client, model="nvidia/example-nemotron")
    ranked = [ScoredTask(task=task("known"), priority_score=0.8)]
    feasibility = [
        evaluate_task_feasibility(
            TaskExecutionProfile(task_id="known", active_minutes=15),
            PlanningContext(available_minutes=30),
        )
    ]

    plan = provider.plan(ranked, PlanningContext(available_minutes=30), feasibility, [])

    assert plan.planner == "nvidia_nemotron"
    assert plan.steps[0].task_id == "known"
    assert client.calls[0]["model"] == "nvidia/example-nemotron"


def test_reasoning_model_must_be_nvidia_nemotron():
    try:
        NebiusPlanningProvider(client=FakeClient("{}"), model="openbmb/MiniCPM-V-4_5")
        assert False, "expected NVIDIA model validation"
    except ValueError as exc:
        assert "NVIDIA Nemotron" in str(exc)


def _provider_inputs(*tasks_with_minutes, available_minutes=60, max_tasks=5):
    context = PlanningContext(
        available_minutes=available_minutes,
        max_tasks=max_tasks,
    )
    ranked = [
        ScoredTask(task=task(identifier, minutes=minutes), priority_score=0.8 - index * 0.1)
        for index, (identifier, minutes) in enumerate(tasks_with_minutes)
    ]
    feasibility = [
        evaluate_task_feasibility(
            TaskExecutionProfile(task_id=identifier, active_minutes=minutes),
            context,
        )
        for identifier, minutes in tasks_with_minutes
    ]
    return context, ranked, feasibility


def test_nemotron_provider_rejects_changed_task_duration():
    content = json.dumps({
        "summary": "Plan",
        "steps": [
            {
                "task_id": "known",
                "order": 1,
                "reason": "do it",
                "active_minutes": 5,
                "passive_minutes": 0,
            }
        ],
        "deferred": [],
    })
    context, ranked, feasibility = _provider_inputs(("known", 15))
    provider = NebiusPlanningProvider(client=FakeClient(content), model="nvidia/example-nemotron")

    try:
        provider.plan(ranked, context, feasibility, [])
        assert False, "expected duration validation failure"
    except ValueError as exc:
        assert "changed task duration" in str(exc)


def test_nemotron_provider_rejects_task_in_steps_and_deferred():
    content = json.dumps({
        "summary": "Plan",
        "steps": [
            {
                "task_id": "known",
                "order": 1,
                "reason": "do it",
                "active_minutes": 15,
                "passive_minutes": 0,
            }
        ],
        "deferred": [{"task_id": "known", "reason": "later"}],
    })
    context, ranked, feasibility = _provider_inputs(("known", 15))
    provider = NebiusPlanningProvider(client=FakeClient(content), model="nvidia/example-nemotron")

    try:
        provider.plan(ranked, context, feasibility, [])
        assert False, "expected disposition validation failure"
    except ValueError as exc:
        assert "conflicting task disposition" in str(exc)


def test_nemotron_provider_rejects_plan_over_available_time():
    content = json.dumps({
        "summary": "Plan",
        "steps": [
            {
                "task_id": "one",
                "order": 1,
                "reason": "first",
                "active_minutes": 15,
                "passive_minutes": 0,
            },
            {
                "task_id": "two",
                "order": 2,
                "reason": "second",
                "active_minutes": 15,
                "passive_minutes": 0,
            },
        ],
        "deferred": [],
    })
    context, ranked, feasibility = _provider_inputs(
        ("one", 15),
        ("two", 15),
        available_minutes=20,
    )
    provider = NebiusPlanningProvider(client=FakeClient(content), model="nvidia/example-nemotron")

    try:
        provider.plan(ranked, context, feasibility, [])
        assert False, "expected active-time validation failure"
    except ValueError as exc:
        assert "available active time" in str(exc)


def test_nemotron_provider_rejects_plan_over_task_limit():
    content = json.dumps({
        "summary": "Plan",
        "steps": [
            {
                "task_id": "one",
                "order": 1,
                "reason": "first",
                "active_minutes": 10,
                "passive_minutes": 0,
            },
            {
                "task_id": "two",
                "order": 2,
                "reason": "second",
                "active_minutes": 10,
                "passive_minutes": 0,
            },
        ],
        "deferred": [],
    })
    context, ranked, feasibility = _provider_inputs(
        ("one", 10),
        ("two", 10),
        available_minutes=30,
        max_tasks=1,
    )
    provider = NebiusPlanningProvider(client=FakeClient(content), model="nvidia/example-nemotron")

    try:
        provider.plan(ranked, context, feasibility, [])
        assert False, "expected task-limit validation failure"
    except ValueError as exc:
        assert "task limit" in str(exc)

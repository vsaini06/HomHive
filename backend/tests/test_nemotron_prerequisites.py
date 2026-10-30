import json
from types import SimpleNamespace

import pytest

from app.coordination.nemotron import advise_coordination


class FakeNebius:
    def __init__(self, response):
        self.requests = []
        self.response = response
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=self.response))])


def plan():
    return {
        "presence": {"state": "UNKNOWN"},
        "availability": {"state": "UNKNOWN"},
        "quiet_hours": {"active": False},
        "preferred_minutes_remaining": 25,
        "tasks": [{"task_id": "sink", "title": "Wash dishes", "priority": 8,
                   "status": "SOON", "reasons": ["Presence is unknown; a photo does not prove someone is home"],
                   "duration_max": None},
                  {"task_id": "closet", "title": "Review closet", "priority": 7,
                   "status": "BLOCKED", "reasons": ["Waiting for your approval before scheduling"],
                   "duration_max": 12}],
    }


def test_waiting_tasks_explain_prerequisites_without_becoming_eligible():
    fake = FakeNebius(json.dumps({
        "selected_task_id": None,
        "summary": "Confirm whether you are home before scheduling chores.",
        "reason": "The available evidence does not establish your presence.",
    }))
    advice = advise_coordination(plan(), client=fake)
    assert advice["selected_task_id"] is None
    assert advice["source"] == "nebius_token_factory_nvidia_nemotron"
    prompt = json.loads(fake.requests[0]["messages"][1]["content"])
    assert prompt["tasks"] == []
    assert len(prompt["waiting_tasks"]) == 2
    assert prompt["waiting_tasks"][0]["status"] == "SOON"
    assert "Presence is unknown" in prompt["waiting_tasks"][0]["reason"]


def test_waiting_task_cannot_be_selected_as_executable():
    fake = FakeNebius(json.dumps({
        "selected_task_id": "sink", "summary": "Wash dishes now.",
        "reason": "The model suggested it.",
    }))
    with pytest.raises(ValueError, match="validation"):
        advise_coordination(plan(), client=fake)

"""Contract tests for bounded, non-coercive planner recovery."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.services.open_world_live import OpenWorldPlanner
from app.services.open_world_planning import Evidence, SceneContext


SCENE = SceneContext(category="unfamiliar room", category_supported=True)
EVIDENCE = [Evidence(id="e1", description="Several objects cover the walking area", provenance="visible", source_id="media1")]


def plan(effort=None):
    return {
        "scene": SCENE.model_dump(mode="json"),
        "evidence": [item.model_dump(mode="json") for item in EVIDENCE],
        "actions": [{
            "action_id": "a1", "title": "Clear walking path",
            "action": "Move loose objects out of the walking path",
            "observation_location": "room floor", "action_location": "room floor",
            "supporting_evidence_ids": ["e1"], "prerequisites": [], "assumptions": [],
            "verification_criteria": "Walking path is clear of loose objects",
            "estimated_effort": effort, "requires_user_confirmation": False,
            "hazard_or_professional_help": False,
        }],
    }


class StubClient:
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def ask(self, *, instruction, payload):
        self.requests.append({"instruction": instruction, "payload": deepcopy(payload)})
        return deepcopy(self.responses[len(self.requests) - 1])


def test_valid_null_effort_uses_one_request():
    client = StubClient([plan(None)])
    result = OpenWorldPlanner(client).propose(EVIDENCE, SCENE)
    assert result.actions[0].estimated_effort is None
    assert len(client.requests) == 1


def test_invalid_string_effort_retries_then_accepts_null():
    client = StubClient([plan("15 minutes"), plan(None)])
    result = OpenWorldPlanner(client).propose(EVIDENCE, SCENE)
    assert result.actions[0].estimated_effort is None
    assert len(client.requests) == 2
    assert "estimated_effort" in client.requests[1]["instruction"]
    assert client.requests[0]["payload"] == client.requests[1]["payload"]


def test_invalid_effort_fails_closed_after_second_attempt():
    client = StubClient([plan(15), plan("15-25 minutes")])
    with pytest.raises(ValidationError):
        OpenWorldPlanner(client).propose(EVIDENCE, SCENE)
    assert len(client.requests) == 2


def test_valid_grounded_estimate_preserved():
    effort = {"minimum_minutes": 5, "maximum_minutes": 10,
              "rationale": "Several visible objects block a small walking path",
              "evidence_ids": ["e1"]}
    client = StubClient([plan(effort)])
    result = OpenWorldPlanner(client).propose(EVIDENCE, SCENE)
    assert result.actions[0].estimated_effort.minimum_minutes == 5
    assert len(client.requests) == 1


def test_no_actions_requires_no_duration():
    payload = plan(None)
    payload["actions"] = []
    client = StubClient([payload])
    assert OpenWorldPlanner(client).propose(EVIDENCE, SCENE).actions == []

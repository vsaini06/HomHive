"""Accuracy-first adapter and autonomous contract tests. No external calls."""
import json
from types import SimpleNamespace

import pytest
from app.services.accuracy_models import AccuracyOpenAIJsonClient, SCHEMAS
from app.services.open_world_live import OpenWorldVision, VisualScene, OpenWorldPlanner


class DummyResponses:
    def __init__(self, reply, status="completed"):
        self.reply = reply
        self.status = status
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(status=self.status, output_text=self.reply)


def adapter(value, status="completed"):
    backend = DummyResponses(json.dumps(value) if not isinstance(value, str) else value, status)
    return AccuracyOpenAIJsonClient(SimpleNamespace(responses=backend), "gpt-6-astra"), backend


def test_scene_structured_schema_is_sent_with_high_effort_and_image():
    client, wire = adapter({"room_category": "kitchen", "claims": []})
    scene = OpenWorldVision(client, None).extract(b"image", "image/jpeg")
    assert scene.room_category == "kitchen"
    call = wire.calls[0]
    assert call["model"] == "gpt-6-astra"
    assert call["reasoning"] == {"effort": "high"}
    assert call["text"]["format"]["strict"] is True
    assert call["text"]["format"]["name"] == "homhive_scene"
    assert call["input"][0]["content"][1]["type"] == "input_image"
    assert call["input"][0]["content"][1]["detail"] == "high"


def test_invalid_or_incomplete_results_do_not_become_hom_hive_evidence():
    for payload, status in [("", "completed"), ("{}", "incomplete"), ("[]", "completed"), ("not json", "completed")]:
        client, _ = adapter(payload, status)
        with pytest.raises((ValueError, json.JSONDecodeError)):
            client.ask(instruction="JSON scene", image=b"pic", schema_kind="scene")


def test_schema_rejects_wrong_tag_and_unsupported_media():
    client, _ = adapter("{}")
    with pytest.raises(ValueError):
        client.ask(instruction="JSON", schema_kind="unknown")
    with pytest.raises(ValueError):
        client.ask(instruction="JSON", image=b"bad", media_type="image/other", schema_kind="scene")


def test_room_pair_uses_both_photographs_with_strict_schema():
    client, wire = adapter({"same_physical_room": False, "explanation": "Different fixed windows"})
    assert client.compare_rooms(b"one", "image/jpeg", b"two", "image/png")["same_physical_room"] is False
    call = wire.calls[0]
    assert call["text"]["format"]["name"] == "homhive_room_pair"
    assert len([i for i in call["input"][0]["content"] if i["type"] == "input_image"]) == 2


def test_two_reviewers_still_both_required_and_disagreement_rejects_claim():
    from app.services.open_world_live import VisualReview, ClaimVerdict
    scene = VisualScene(room_category="garage", claims=[{"id":"e1","description":"Several tools scattered on garage floor"}])
    class Independent:
        def ask(self, **kwargs):
            return {"room_supported":True,"room_category":"garage","claims":[{"id":"e1","supported":True}]}
    second, _ = adapter({"room_supported":True,"room_category":"garage","claims":[{"id":"e1","supported":False}]})
    review = OpenWorldVision(None, Independent(), second).verify(scene,b"image","image/jpeg")
    assert review.claims[0].supported is False


def test_planner_uses_action_schema_without_changing_action_validation():
    client, wire = adapter({"actions":[]})
    result = OpenWorldPlanner(client).propose([], __import__('app.services.open_world_planning', fromlist=['SceneContext']).SceneContext())
    assert result.actions == []
    assert wire.calls[0]["text"]["format"]["name"] == "homhive_actions"


def test_supported_json_schemas_use_required_fields_and_no_extras():
    def walk(node):
        if not isinstance(node, dict): return
        if node.get('type') == 'object':
            assert node['additionalProperties'] is False
            assert set(node['required']) == set(node['properties'])
            for v in node['properties'].values():walk(v)
        for path in ('items',):
            if path in node:walk(node[path])
        for alt in node.get('anyOf',[]):walk(alt)
    for s in SCHEMAS.values():walk(s)


def test_old_pipeline_does_not_pass_new_schema_kwarg():
    class OldClient:
        def ask(self, *, instruction, payload=None, image=None, media_type="image/jpeg"):
            return {"room_category":None,"claims":[]}
    assert OpenWorldVision(OldClient(), None).extract(b"image","image/jpeg").claims == []

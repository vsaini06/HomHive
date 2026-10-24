"""Anthropic reviewer retry and safe diagnostics regression tests."""
import json
from types import SimpleNamespace
import pytest
from app.vision.anthropic_verification import AnthropicImageVerifier
from app.vision.provider import VisionExtraction, VisionCandidate
from app.models import ConditionType

GOOD = {"space_category": "kitchen", "room_supported": True, "claims": [
    {"category":"dish_load", "visible":True, "evidence_supported":True, "workload_supported":True}
]}

def proposed():
    return VisionExtraction(candidates=[VisionCandidate(category=ConditionType.DISH_LOAD,
        value=0.8, location="unknown", visible_evidence="visible dishes")],
        needs_review=False, space_category="kitchen")

class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.max_tokens = []
    def post(self, *a, **kw):
        self.max_tokens.append(kw["json"]["max_tokens"])
        payload = next(self.replies)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

def reply(text, stop="end_turn"):
    return {"stop_reason":stop, "content":[{"type":"text","text":text}]}

def test_malformed_json_retries_once_and_recovers():
    client = FakeClient([reply('{"claims":'),reply(json.dumps(GOOD))])
    result=AnthropicImageVerifier(model="test",api_key="fake",client=client).review(
        b"abc","image/jpeg",proposed())
    assert result.room_supported is True
    assert client.max_tokens == [1600,2400]

def test_unparseable_twice_stays_failure():
    client=FakeClient([reply('no JSON'),reply('still no JSON')])
    with pytest.raises(json.JSONDecodeError):
        AnthropicImageVerifier(model="test",api_key="fake",client=client).review(
            b"abc","image/jpeg",proposed())
    assert len(client.max_tokens)==2

def test_truncated_json_retries():
    client=FakeClient([reply('{"claims":',"max_tokens"), reply(json.dumps(GOOD))])
    result=AnthropicImageVerifier(model="test",api_key="fake",client=client).review(
        b"abc","image/jpeg",proposed())
    assert result.room_supported

def test_invalid_structured_claim_never_passes():
    invalid = {**GOOD, "claims":[{**GOOD["claims"][0],"visible":"uncertain"}]}
    client=FakeClient([reply(json.dumps(invalid)), reply(json.dumps(invalid))])
    with pytest.raises(Exception):
        AnthropicImageVerifier(model="test",api_key="fake",client=client).review(
            b"abc","image/jpeg",proposed())

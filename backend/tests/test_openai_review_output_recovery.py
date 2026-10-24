from types import SimpleNamespace
import json
import pytest
from app.vision.verification import OpenAIImageVerifier
from app.vision.provider import VisionExtraction, VisionCandidate, SpaceCategory
from app.models import ConditionType


def proposed():
    return VisionExtraction(candidates=[VisionCandidate(category=ConditionType.LAUNDRY_LOAD, value=0.8, location="unknown", visible_evidence="basket")], needs_review=False, space_category=SpaceCategory.LAUNDRY_ROOM)


def response(payload, reason="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=payload), finish_reason=reason)])


def valid():
    return json.dumps({"space_category":"laundry_room", "room_supported":True, "claims":[{"category":"laundry_load", "visible":True, "evidence_supported":True, "workload_supported":True}]})


class FakeClient:
    def __init__(self, results):
        self.results=iter(results)
        self.calls=[]
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self.results)


def test_valid_review_has_one_call():
    client=FakeClient([response(valid())])
    assert OpenAIImageVerifier(model="mock",client=client).review(b"img","image/jpeg",proposed()).room_supported
    assert len(client.calls)==1


def test_retries_bad_json_once():
    client=FakeClient([response('{"broken":'),response(valid())])
    assert OpenAIImageVerifier(model="mock",client=client).review(b"img","image/jpeg",proposed()).room_supported
    assert len(client.calls)==2


def test_retries_schema_violation_once():
    client=FakeClient([response('{"space_category":"laundry_room","room_supported":true,"claims":[{"category":"laundry_load","visible":"maybe","evidence_supported":true,"workload_supported":true}]}'),response(valid())])
    assert OpenAIImageVerifier(model="mock",client=client).review(b"img","image/jpeg",proposed()).room_supported
    assert len(client.calls)==2


def test_truncation_requires_retry():
    client=FakeClient([response(valid(),"length"), response(valid())])
    assert OpenAIImageVerifier(model="mock",client=client).review(b"img","image/jpeg",proposed()).room_supported
    assert len(client.calls)==2


def test_repeated_invalid_review_fails_closed():
    client=FakeClient([response('not json'), response('not json')])
    with pytest.raises(json.JSONDecodeError):
        OpenAIImageVerifier(model="mock",client=client).review(b"img","image/jpeg",proposed())
    assert len(client.calls)==2

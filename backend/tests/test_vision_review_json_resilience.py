import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from app.vision.verification import parse_review_json, OpenAIImageVerifier
from app.vision.anthropic_verification import AnthropicImageVerifier
from app.vision.provider import VisionExtraction, VisionCandidate
from app.models import ConditionType

GOOD = {"space_category":"kitchen", "room_supported":True, "claims":[
    {"category":"dish_load","visible":True,"evidence_supported":True,"workload_supported":True}
]}


def prediction():
    return VisionExtraction(candidates=[VisionCandidate(category=ConditionType.DISH_LOAD,
        value=0.8,location="unknown",visible_evidence="visible dishes")],
        needs_review=False,space_category="kitchen")


def test_fences_with_whitespace_and_strict_schema():
    assert parse_review_json("```json\n"+json.dumps(GOOD)+"\n```").room_supported
    with pytest.raises((ValueError, ValidationError)):
        parse_review_json('Here is the result: '+json.dumps(GOOD))
    with pytest.raises(ValidationError):
        parse_review_json(json.dumps({**GOOD,"claims":[{**GOOD["claims"][0],"visible":"maybe"}]}))


def test_openai_fenced_review():
    def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="```json\n"+json.dumps(GOOD)+"\n```"))])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    assert OpenAIImageVerifier(model="test",client=client).review(b"abc","image/jpeg",prediction()).room_supported


def test_anthropic_multiple_text_blocks():
    value=json.dumps(GOOD)
    class Client:
        def post(self, *args, **kwargs):
            return SimpleNamespace(raise_for_status=lambda:None,
                json=lambda:{"content":[{"type":"text","text":value[:25]},
                                         {"type":"text","text":value[25:]}]})
    result=AnthropicImageVerifier(model="test",api_key="fake",client=Client()).review(b"abc","image/jpeg",prediction())
    assert result.room_supported

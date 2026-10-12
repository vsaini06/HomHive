from types import SimpleNamespace

from app.vision.provider import NebiusVisionProvider


class CapturingClient:
    def __init__(self, response):
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.response = response

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.response))])


def test_dish_workload_rubric_is_explicit_in_provider_request():
    client = CapturingClient('{"candidates":[{"category":"dish_load","value":0.2,"location":"kitchen","visible_evidence":"One bowl and glass"}],"needs_review":false}')
    result = NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')
    prompt = client.requests[0]['messages'][0]['content']
    assert 'dishwashing WORKLOAD' in prompt
    assert 'Do not assign 1.0 merely because any dirty dish is visible' in prompt
    assert '1.0 = extreme visible dishwashing workload only' in prompt
    assert result.candidates[0].value == 0.2


def test_revised_rubric_keeps_missing_categories_unknown():
    client = CapturingClient('{"candidates":[{"category":"dish_load","value":0.0,"location":"kitchen","visible_evidence":"Empty sink"}],"needs_review":false}')
    result = NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')
    prompt = client.requests[0]['messages'][0]['content']
    assert 'A missing or out-of-frame target is UNKNOWN, not zero' in prompt
    assert 'Never provide a confidence score' in prompt
    assert len(result.candidates) == 1
    assert not hasattr(result.candidates[0], 'confidence')

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.vision import NebiusVisionProvider, VisionService, VisionExtraction


class FakeClient:
    def __init__(self, text):
        self.requests = []
        self.text = text
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.text))])


def test_nebius_image_request_parses_candidates():
    client = FakeClient('{"candidates": [{"category": "dish_load", "value": 0.8, "location": "kitchen", "visible_evidence": "Visible sink with stacked dishes"}], "needs_review": false}')
    output = NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')
    assert output.candidates[0].value == 0.8
    assert client.requests[0]['model'] == 'openbmb/MiniCPM-V-4_5'
    assert client.requests[0]['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert not hasattr(output.candidates[0], 'confidence')
    assert output.candidates[0].visible_evidence == 'Visible sink with stacked dishes'
    assert 'A missing or out-of-frame target is UNKNOWN, not zero' in client.requests[0]['messages'][0]['content']


def test_uncertain_image_produces_no_observation():
    client = FakeClient('{"candidates": [], "needs_review": true}')
    output = NebiusVisionProvider(client=client).extract(b'\x89PNG\r\n\x1a\nexample', 'image/png', 'laundry_room')
    assert output.needs_review
    assert not output.candidates


@pytest.mark.parametrize('reply', [
    'not json',
    '{"candidates":[{"category":"dish_load","value":1.8,"location":"kitchen"}],"needs_review":false}',
    '{"candidates":[{"category":"maintenance_status","value":0.8,"location":"kitchen"}],"needs_review":false}',
    '{"candidates":[],"needs_review":false,"confidence":0.9}',
])
def test_invalid_provider_responses_fail_closed(reply):
    client = FakeClient(reply)
    with pytest.raises(ValueError):
        NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')


def test_rejects_unsupported_image():
    with pytest.raises(ValueError):
        NebiusVisionProvider(client=FakeClient('{}')).extract(b'data', 'text/plain', 'kitchen')


def test_household_scoped_media_lookup():
    class Media:
        def __init__(self):
            self.calls = []

        def get_image(self, household_id, media_id):
            self.calls.append((household_id, media_id))
            return None

    media = Media()
    service = VisionService(media, NebiusVisionProvider(client=FakeClient('{}')))
    assert service.inspect_image('home_a', 'missing', 'kitchen') is None
    assert media.calls == [('home_a', 'missing')]


def test_extra_fields_not_accepted():
    with pytest.raises(ValidationError):
        VisionExtraction.model_validate({'candidates': [], 'needs_review': True, 'confidence': 0.9})


def test_visible_empty_sink_only_returns_dishes():
    client = FakeClient('{"candidates": [{"category": "dish_load", "value": 0.0, "location": "kitchen", "visible_evidence": "Both visible sink basins are empty"}], "needs_review": false}')
    output = NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')
    assert len(output.candidates) == 1
    assert output.candidates[0].category.value == 'dish_load'
    assert output.candidates[0].value == 0.0


def test_missing_visible_evidence_is_rejected():
    client = FakeClient('{"candidates": [{"category": "laundry_load", "value": 0.0, "location": "kitchen"}], "needs_review": false}')
    with pytest.raises(ValueError, match='Invalid vision provider response'):
        NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')


def test_blank_visible_evidence_is_rejected():
    client = FakeClient('{"candidates": [{"category": "dish_load", "value": 0, "location": "kitchen", "visible_evidence": "  "}], "needs_review": false}')
    with pytest.raises(ValueError, match='empty visual evidence'):
        NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')


def test_duplicate_category_is_rejected():
    client = FakeClient('{"candidates": [{"category": "dish_load", "value": 0, "location": "kitchen", "visible_evidence": "Empty visible sink"}, {"category": "dish_load", "value": 0.2, "location": "kitchen", "visible_evidence": "One visible dish"}], "needs_review": false}')
    with pytest.raises(ValueError, match='Duplicate vision categories'):
        NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')


def test_markdown_fenced_provider_json_is_accepted():
    client = FakeClient('```json\n{"candidates": [{"category": "dish_load", "value": 0.5, "location": "kitchen", "visible_evidence": "Several dishes in sink"}], "needs_review": false, "space_category": "kitchen"}\n```')
    result = NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')
    assert result.candidates[0].value == 0.5
    assert result.space_category.value == 'kitchen'


def test_invalid_fenced_provider_json_still_rejected():
    client = FakeClient('```json\n{"candidates": [], "needs_review": false}\n```')
    with pytest.raises(ValueError, match='Inconsistent vision review status'):
        NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'kitchen')


def test_candidates_needing_review_are_valid_primary_evidence():
    client = FakeClient('{"candidates":[{"category":"dish_load","value":0.6,"location":"unknown","visible_evidence":"Several dishes in visible sink"}],"needs_review":true,"space_category":"kitchen"}')
    result = NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'unknown')
    assert result.needs_review is True
    assert len(result.candidates) == 1
    assert result.space_category.value == 'kitchen'


def test_empty_candidates_without_review_still_rejected():
    client = FakeClient('{"candidates":[],"needs_review":false,"space_category":"kitchen"}')
    with pytest.raises(ValueError, match='Inconsistent vision review status'):
        NebiusVisionProvider(client=client).extract(b'\xff\xd8\xffexample', 'image/jpeg', 'unknown')


def test_inferred_room_cannot_override_requested_physical_location():
    client = FakeClient('{"candidates":[{"category":"dish_load","value":0.8,"location":"kitchen","visible_evidence":"Visible stacked dishes in sink"}],"needs_review":false,"space_category":"kitchen"}')
    result = NebiusVisionProvider(client=client).extract(b"\xff\xd8\xffimage", "image/jpeg", "unknown")
    assert result.candidates[0].location == "unknown"
    assert result.space_category.value == "kitchen"

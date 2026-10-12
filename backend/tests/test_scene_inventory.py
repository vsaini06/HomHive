import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.vision.scene import NebiusSceneProvider, SceneEntity, SceneInventory


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def inventory_reply(entities, location='kitchen', needs_review=False):
    return json.dumps({'location': location, 'entities': entities, 'needs_review': needs_review})


def entity(label, condition='not_assessed', condition_evidence=None):
    return {'label': label, 'area': 'countertop', 'evidence': f'{label} visible on counter', 'condition': condition, 'condition_evidence': condition_evidence}


def test_multiple_objects_without_invented_conditions():
    client = FakeClient(inventory_reply([entity('potted plant'), entity('sponge'), entity('mug', 'visibly_dirty', 'food residue on mug')]))
    result = NebiusSceneProvider(client=client).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')
    assert len(result.entities) == 3
    assert result.entities[0].condition == 'not_assessed'
    assert result.entities[2].condition_evidence == 'food residue on mug'
    assert 'Do not estimate household workload' in client.calls[0]['messages'][0]['content']


def test_empty_scene_requires_review():
    with pytest.raises(ValidationError):
        SceneInventory(location='kitchen', entities=[], needs_review=False)
    assert SceneInventory(location='kitchen', entities=[], needs_review=True).needs_review


@pytest.mark.parametrize('bad', [
    entity('plant', 'visibly_stressed'),
    entity('plant', 'unknown', 'yellow leaves'),
    {**entity('plant'), 'evidence': ' '},
])
def test_unsupported_condition_claim_is_rejected(bad):
    with pytest.raises(ValidationError):
        SceneEntity.model_validate(bad)


def test_location_mismatch_rejected():
    client = FakeClient(inventory_reply([entity('mug')], location='bathroom'))
    with pytest.raises(ValueError, match='Scene location mismatch'):
        NebiusSceneProvider(client=client).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')


def test_extra_fields_rejected():
    bad = entity('plant')
    bad['confidence'] = 0.99
    with pytest.raises(ValueError, match='Invalid scene provider response'):
        NebiusSceneProvider(client=FakeClient(inventory_reply([bad]))).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')


def test_image_validation_precedes_provider_call():
    client = FakeClient(inventory_reply([entity('plant')]))
    with pytest.raises(ValueError, match='Unsupported image content'):
        NebiusSceneProvider(client=client).inventory(b'invalid', 'image/jpeg', 'kitchen')
    assert not client.calls


def test_unparseable_response_rejected():
    with pytest.raises(ValueError, match='Invalid scene provider response'):
        NebiusSceneProvider(client=FakeClient('not json')).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')


def test_missing_model_location_is_supplied_by_application():
    client = FakeClient(json.dumps({'entities': [entity('sink')], 'needs_review': False}))
    result = NebiusSceneProvider(client=client).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')
    assert result.location == 'kitchen'
    assert len(result.entities) == 1
    assert not result.needs_review


def test_unsupported_assessment_is_rejected_but_object_is_retained():
    claim = entity('plant', 'visibly_stressed', None)
    client = FakeClient(inventory_reply([entity('sink'), claim]))
    result = NebiusSceneProvider(client=client).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')
    assert len(result.entities) == 2
    assert result.entities[1].condition == 'unknown'
    assert result.entities[1].condition_evidence is None
    assert result.needs_review
    assert result.rejected_assessments[0].claimed_condition == 'visibly_stressed'
    assert result.rejected_assessments[0].entity_index == 1


def test_blank_evidence_does_not_validate_an_assessment():
    claim = entity('mug', 'visibly_dirty', '   ')
    result = NebiusSceneProvider(client=FakeClient(inventory_reply([claim]))).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')
    assert result.entities[0].condition == 'unknown'
    assert len(result.rejected_assessments) == 1


def test_malformed_entity_does_not_get_salvaged():
    claim = entity('plant', 'visibly_stressed', None)
    claim['unexpected'] = 'field'
    with pytest.raises(ValueError, match='Invalid scene provider response'):
        NebiusSceneProvider(client=FakeClient(inventory_reply([claim]))).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')


def test_optional_location_cannot_override_trusted_location():
    result = NebiusSceneProvider(client=FakeClient(inventory_reply([entity('sink')]))).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')
    assert result.location == 'kitchen'


def test_fenced_json_is_accepted():
    payload = inventory_reply([entity('sink')])
    content = f'```json\n{payload}\n```'
    result = NebiusSceneProvider(client=FakeClient(content)).inventory(b'\xff\xd8\xffsample', 'image/jpeg', 'kitchen')
    assert result.entities[0].label == 'sink'

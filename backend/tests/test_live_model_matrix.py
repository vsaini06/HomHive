"""No-network unit coverage for the billable, opt-in live model evaluation runner."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import live_model_matrix as suite


def prediction(change, person=None, added=None, removed=None):
    return {'change_type':change,'summary':'Visual difference grounded in images',
            'changed_objects':['sink'],'physical_person_added':person,
            'added_physical_objects':added if added is not None else [],
            'removed_physical_objects':removed if removed is not None else []}


@pytest.mark.parametrize('category',suite.CATEGORIES[:10])
def test_every_supported_change_kind_can_be_scored(category):
    kwargs={'person':True} if category=='human_addition' else {}
    assert suite.validate_pair(prediction(category,**kwargs),category)[0]


@pytest.mark.parametrize('category',['depiction','reflection','addition'])
def test_never_add_physical_person_from_screen_photo_mannequin(category):
    passed,reason=suite.validate_pair(prediction(category,person=True),category)
    assert not passed and reason=='false_physical_person_added'


@pytest.mark.parametrize('category',['depiction','reflection'])
def test_no_physical_objects_created_by_screen_or_reflection(category):
    passed,reason=suite.validate_pair(prediction(category,added=['plant']),category)
    assert not passed and reason=='depiction_or_reflection_counted_as_new_physical_object'


def test_crop_cannot_be_interpreted_as_physical_removal():
    assert not suite.validate_pair(prediction('crop',removed=['bed']), 'crop')[0]


def test_real_person_addition_requires_positive_presence_evidence():
    assert not suite.validate_pair(prediction('human_addition',person=None),'human_addition')[0]


def test_detects_wrong_change_type():
    assert suite.validate_pair(prediction('removal'),'lighting') == (False,'change_type_mismatch')


def test_strict_pair_schema_requires_nonempty_summary_and_lists():
    d=prediction('condition');d['summary']=''
    assert not suite.validate_pair(d,'condition')[0]
    d=prediction('condition');d['added_physical_objects']=42
    assert not suite.validate_pair(d,'condition')[0]


def test_json_parser_plain_fenced_reasoning_and_embedded_content():
    for value,recovered in [(' {"decision":"defer"}',False),
                             ('```json\n{"decision":"defer"}\n```',True),
                             ('<think>Reasoning</think>\n{"decision":"defer"}',True),
                             ('I think: {"decision":"defer"} end.',True)]:
        obj,was_recovered=suite.parse_json_object(value)
        assert obj=={'decision':'defer'} and was_recovered is recovered


def test_invalid_json_remains_error():
    with pytest.raises(suite.ProviderError,match='invalid_json'):
        suite.parse_json_object('Here is JSON: {broken json}')


@pytest.mark.parametrize(('first','second','category','direction','expected'),[
    ({'dish_load':0.15},{'dish_load':0.75},'dish_load','increase',True),
    ({'dish_load':0.4},{'dish_load':0.41},'dish_load','increase',False),
    ({'dish_load':0.8},{'dish_load':0.1},'dish_load','decrease',True),
    ({'laundry_load':0.8},{},'laundry_load','decrease_or_absent',True),
    ({},{'laundry_load':0.8},'laundry_load','increase',False),
    ({'dish_load':0.9},{},'dish_load','decrease',False),
])
def test_real_production_change_scoring(first,second,category,direction,expected):
    assert suite.evaluate_condition_change(first,second,category,direction)[0] is expected


def test_quick_selection_covers_ten_change_categories():
    cases=json.loads(Path(suite.__file__).with_name('model_eval_cases.json').read_text())['pairs']
    sample=suite.select_pairs(cases,12)
    assert len(sample)==12
    assert len({c['expected'] for c in sample})==10


def test_manifest_28_verified_links_and_no_traversal():
    cases=json.loads(Path(suite.__file__).with_name('model_eval_cases.json').read_text())
    assert len(cases['pairs'])==28
    assert len(cases['standalone'])==12
    assert set(cases['missing_pairs'])=={'NV06','NV09','NV18','NV32'}
    assert all('/' not in c['base'] and '..' not in c['base'] for c in cases['pairs'])
    assert all(c['expected'] in suite.CATEGORIES for c in cases['pairs'])


def test_blinded_comparison_prompt_does_not_disclose_ground_truth():
    assert 'NV01' not in suite.PAIR_PROMPT
    assert 'dirty_dish_group' not in suite.PAIR_PROMPT
    assert 'selected carton' not in suite.PAIR_PROMPT
    assert 'ground truth' not in suite.PAIR_PROMPT.lower()


def test_single_image_schema_checks_missing_person_flags():
    valid={'room_category':'kitchen','visible_objects':['sink'],'physically_present_person':None,
           'screen_or_photo_person_only':False,'condition_evidence':'Few dishes'}
    assert suite.validate_single(valid)[0]
    bad=dict(valid,screen_or_photo_person_only='false')
    assert not suite.validate_single(bad)[0]


class FakeGateway:
    def __init__(self, result):self.result=result;self.requests=[]
    def post(self,url,payload,headers):
        self.requests.append((url,payload,headers))
        return self.result


def test_vision_request_contains_two_labeled_images_and_not_expected_label(monkeypatch):
    monkeypatch.setenv('NEBIUS_API_KEY','test_key')
    fake=FakeGateway({'choices':[{'message':{'content':json.dumps(prediction('lighting'))}}]})
    result,_=suite.image_completion(fake,'nebius',[('image/jpeg','AAAA'),('image/jpeg','BBBB')],suite.PAIR_PROMPT)
    assert result['change_type']=='lighting'
    payload=fake.requests[0][1]
    chunks=payload['messages'][-1]['content']
    assert len([c for c in chunks if c['type']=='image_url'])==2
    assert any(c.get('text')=='Photo A' for c in chunks)
    assert any(c.get('text')=='Photo B' for c in chunks)
    assert 'NV01' not in json.dumps(payload)


def test_anthropic_payload_uses_explicit_media_and_source(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','test_key')
    fake=FakeGateway({'content':[{'type':'text','text':json.dumps(prediction('occlusion'))}]})
    suite.image_completion(fake,'anthropic',[('image/jpeg','AAAA'),('image/jpeg','BBBB')],suite.PAIR_PROMPT)
    blocks=fake.requests[0][1]['messages'][0]['content']
    assert len([x for x in blocks if x['type']=='image'])==2
    assert all(x['source']['media_type']=='image/jpeg' for x in blocks if x['type']=='image')

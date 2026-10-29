from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService
from app.coordination.nemotron import advise_coordination


def new_jobs():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine)
    return AutonomousJobService(sessionmaker(engine, expire_on_commit=False))


class Media:
    def get_image(self, household_id, media_id):
        assert household_id == 'my-home'
        return SimpleNamespace(content_type='image/jpeg'), media_id.encode()


def scan_ok(**kwargs):
    return {'status': 'reviewed', 'room_category': 'bedroom', 'created': [],
            'existing': [], 'review_summary': {'room_identity_source': 'model_verified'}}


def test_recent_completed_view_anchors_room_identity_without_reprompt():
    jobs = new_jobs()
    rid = jobs.enroll('my-home', 'base')
    first = jobs.enqueue('my-home', 'different-angle')
    jobs.finish(first, 'held_unverified_room')
    jobs.assign_existing_room('my-home', 'different-angle', rid)
    assert jobs.process_one(media=Media(), bridge=None, build_pipeline=lambda: None, scan=scan_ok) == 'completed'
    assert jobs.recent_room_views('my-home')[rid] == ['different-angle']
    second = jobs.enqueue('my-home', 'new-lighting')
    calls = []
    def compare(vision, reference, reference_type, candidate, candidate_type):
        calls.append(reference)
        return reference == b'different-angle'
    with patch('app.vision.autonomous_api.verify_room_pair', compare):
        returned = []
        def capture(**kwargs):
            returned.append(kwargs)
            return scan_ok(**kwargs)
        assert jobs.process_one(media=Media(), bridge=None,
               build_pipeline=lambda: (SimpleNamespace(independent=None), None, None), scan=capture) == 'completed'
    assert calls == [b'base', b'different-angle']
    assert returned[0]['verified_room_evidence'] is True
    assert returned[0]['reference_media_id'] == 'base'
    assert jobs.jobs('my-home')[0]['room_id'] == rid


def test_conflicting_room_matches_remain_held():
    jobs = new_jobs()
    jobs.enroll('my-home', 'bedroom1')
    jobs.enroll('my-home', 'bedroom2')
    jobs.enqueue('my-home', 'uncertain')
    with patch('app.vision.autonomous_api.verify_room_pair', return_value=True):
        result = jobs.process_one(media=Media(), bridge=None,
            build_pipeline=lambda: (SimpleNamespace(independent=None), None, None), scan=scan_ok)
    assert result == 'held_unverified_room'
    assert jobs.jobs('my-home')[0]['room_id'] is None


def plan(statuses):
    return {'presence': {'state': 'HOME'}, 'availability': {'state': 'FREE'},
            'quiet_hours': {'active': False}, 'preferred_minutes_remaining': 30,
            'tasks': [{'task_id': str(i), 'title': f'Existing task {i}', 'priority': 10,
                       'status': status, 'reasons': ['Known constraint'],
                       'duration_max': 15} for i, status in enumerate(statuses)]}


class FakeClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.content = content
        self.requests = []
    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def test_nebius_accepts_only_feasible_existing_task():
    client = FakeClient('{"selected_task_id":"0","summary":"Choose the approved first task.","reason":"It is currently safe and feasible."}')
    result = advise_coordination(plan(['NOW', 'BLOCKED']), client=client, model='nvidia/example-nemotron')
    assert result['selected_task_id'] == '0'
    assert result['source'] == 'nebius_token_factory_nvidia_nemotron'
    assert len(client.requests) == 1


@pytest.mark.parametrize('selected', ['1', 'unknown'])
def test_nebius_rejects_blocked_or_invented_ids(selected):
    client = FakeClient('{"selected_task_id":"'+selected+'","summary":"This is a model explanation.","reason":"The selected work is currently useful."}')
    with pytest.raises(ValueError, match='validation'):
        advise_coordination(plan(['NOW', 'BLOCKED']), client=client, model='nvidia/example-nemotron')


def test_empty_tasks_require_no_api_call():
    result = advise_coordination(plan([]))
    assert result['source'] == 'deterministic_empty_plan'
    assert result['selected_task_id'] is None


def test_nebius_reasoning_has_output_budget_and_only_receives_now_options():
    client = FakeClient('{"selected_task_id":null,"summary":"No executable tasks now.","reason":"All current tasks require approval."}')
    result = advise_coordination(plan(['BLOCKED', 'SOON']), client=client, model='nvidia/example-nemotron')
    assert result['selected_task_id'] is None
    request = client.requests[0]
    assert request['max_tokens'] >= 2048
    import json
    payload = json.loads(request['messages'][1]['content'])
    assert payload['tasks'] == []
    assert payload['ineligible_task_counts']['BLOCKED'] == 1


def test_nebius_accepts_fenced_json_without_weakening_task_checks():
    client = FakeClient('```json\n{"selected_task_id":"0","summary":"Do this task.","reason":"The duration and presence allow it."}\n```')
    response = advise_coordination(plan(['NOW']), client=client, model='nvidia/example-nemotron')
    assert response['selected_task_id'] == '0'


def test_nebius_rejects_missing_final_answer_with_safe_reason_code():
    client = FakeClient(None)

    with patch('app.coordination.nemotron.logger.warning') as warning:
        with pytest.raises(ValueError, match='validation'):
            advise_coordination(plan(['BLOCKED']), client=client, model='nvidia/example-nemotron')
    warning.assert_called_once_with('Nemotron advice rejected: %s', 'empty_final_answer')


def test_nebius_rejects_invalid_json_and_blocked_ids():
    for response in ('not json', '{"selected_task_id":"0","summary":"do it","reason":"now"}'):
        client = FakeClient(response)
        with pytest.raises(ValueError, match='validation'):
            advise_coordination(plan(['BLOCKED']), client=client, model='nvidia/example-nemotron')


def test_nebius_accepts_delimited_reasoning_but_validates_final_choice():
    client = FakeClient('<think>Reasoning details</think>\n{"selected_task_id":"0","summary":"Choose the approved first task.","reason":"It is executable now."}')
    result = advise_coordination(plan(['NOW']), client=client, model='nvidia/example-nemotron')
    assert result['selected_task_id'] == '0'

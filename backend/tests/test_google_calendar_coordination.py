"""Verify read-only Calendar constraints never authorize unsafe work."""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import pytest
from app.coordination.google_calendar import freebusy_intervals, apply_freebusy, GOOGLE_FREEBUSY_URL

NOW = datetime(2026, 10, 29, 18, 0, tzinfo=timezone.utc)


def _plan():
    return {"preferred_minutes_remaining": 36, "tasks": [
        {"task_id": "plant", "title": "Check plant", "priority": 3, "status": "NOW", "duration_max": 10, "reasons": ["ready"]},
        {"task_id": "wash", "title": "Wash item", "priority": 2, "status": "NOW", "duration_max": 35, "reasons": ["ready"]},
        {"task_id": "unknown", "title": "Look at shelf", "priority": 1, "status": "SOON", "duration_max": None, "reasons": ["missing duration"]},
        {"task_id": "blocked", "title": "Repair", "priority": 9, "status": "BLOCKED", "duration_max": 5, "reasons": ["not approved"]}],
        "groups": {"NOW": 2, "SOON": 1, "DEFERRED": 0, "BLOCKED": 1}, "source_note": "manual"}


def test_calendar_busy_event_defers_only_conflicting_task():
    plan = _plan()
    result = apply_freebusy(plan, [(NOW + timedelta(minutes=20), NOW + timedelta(minutes=40))], NOW, 60)
    assert result["calendar"]["effective_work_minutes"] == 20
    assert result["groups"] == {"NOW": 1, "SOON": 1, "DEFERRED": 1, "BLOCKED": 1}
    assert next(task for task in result["tasks"] if task["task_id"] == "wash")["status"] == "DEFERRED"
    assert plan["tasks"][1]["status"] == "NOW"


def test_busy_now_prevents_execution_even_when_manual_status_is_free():
    result = apply_freebusy(_plan(), [(NOW - timedelta(minutes=2), NOW + timedelta(minutes=15))], NOW, 60)
    assert result["calendar"]["busy_now"] is True
    assert result["groups"]["NOW"] == 0
    assert result["groups"]["BLOCKED"] == 1


def test_no_events_does_not_create_new_ready_tasks():
    result = apply_freebusy(_plan(), [], NOW, 60)
    assert result["calendar"]["conflict_free_minutes"] == 60
    assert result["calendar"]["effective_work_minutes"] == 36
    assert next(t for t in result["tasks"] if t["task_id"] == "unknown")["status"] == "SOON"


def test_calendar_freebusy_request_uses_only_primary_scope_and_interval():
    response = Mock(status_code=200)
    response.json.return_value = {"calendars": {"primary": {"busy": [{"start": (NOW + timedelta(minutes=5)).isoformat(), "end": (NOW + timedelta(minutes=25)).isoformat()}]}}}
    client = Mock()
    client.post.return_value = response
    intervals = freebusy_intervals("opaque-token", NOW, 60, client=client)
    assert len(intervals) == 1
    args, kw = client.post.call_args
    assert args[0] == GOOGLE_FREEBUSY_URL
    assert kw["json"]["items"] == [{"id": "primary"}]
    assert kw["headers"]["Authorization"] == "Bearer opaque-token"


def test_calendar_authorization_failure_must_not_report_availability():
    client = Mock()
    client.post.return_value = Mock(status_code=401)
    with pytest.raises(ValueError, match="authorization"):
        freebusy_intervals("opaque", NOW, 45, client=client)

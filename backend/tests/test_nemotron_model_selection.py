from types import SimpleNamespace
import json

from app.coordination.nemotron import advise_coordination


class StubNebius:
    def __init__(self, content: str):
        self.requests = []
        self.content = content
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))])


def _plan(statuses):
    return {"presence": {"state": "HOME"}, "availability": {"state": "FREE"},
            "quiet_hours": {"active": False}, "preferred_minutes_remaining": 30,
            "tasks": [{"task_id": str(i), "title": f"Work {i}", "priority": 10,
                       "status": state, "reasons": ["Known state"], "duration_max": 10}
                      for i, state in enumerate(statuses)]}


def test_advice_defaults_to_super_model(monkeypatch):
    monkeypatch.delenv("NEBIUS_ADVICE_MODEL", raising=False)
    client = StubNebius('{"selected_task_id":"0","summary":"Start with the first task.","reason":"It fits your current availability."}')
    result = advise_coordination(_plan(["NOW", "BLOCKED"]), client=client)
    assert client.requests[0]["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert result["model"] == client.requests[0]["model"]
    assert all(task["task_id"] == "0" for task in json.loads(client.requests[0]["messages"][1]["content"])["tasks"])


def test_advice_allows_explicit_lightning_fallback(monkeypatch):
    monkeypatch.setenv("NEBIUS_ADVICE_MODEL", "nvidia/Nemotron-3_5-Lightning")
    client = StubNebius('{"selected_task_id":null,"summary":"Nothing is ready right now.","reason":"Wait until blocked tasks are approved."}')
    result = advise_coordination(_plan(["BLOCKED"]), client=client)
    assert client.requests[0]["model"] == "nvidia/Nemotron-3_5-Lightning"
    assert result["selected_task_id"] is None


def test_advice_never_selects_blocked_task(monkeypatch):
    monkeypatch.delenv("NEBIUS_ADVICE_MODEL", raising=False)
    client = StubNebius('{"selected_task_id":"1","summary":"Choose the blocked task.","reason":"It looks useful."}')
    try:
        advise_coordination(_plan(["NOW", "BLOCKED"]), client=client)
    except ValueError as exc:
        assert "validation" in str(exc)
    else:
        raise AssertionError("Blocked task unexpectedly accepted")

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.services.autonomous_lifecycle import (
    AutonomousLifecycle, EvidenceReference, RoomContinuity, VerifiedAction,
    ReviewedOutcome, OutcomeVerdict, recommended_window,
)


@pytest.fixture
def service():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return AutonomousLifecycle(sessionmaker(bind=engine, expire_on_commit=False))


def room(room_id="closet"):
    return RoomContinuity(physical_room_id=room_id, same_physical_room_verified=True,
                          reason="Independent evidence confirms this exact space")


def action(*, media_id="original", confirmed=False, key="organize-floor-task"):
    return VerifiedAction(action_key=key, title="Sort closet floor",
        action="Review and sort items on the visible closet floor",
        verification_criteria="Original closet floor clutter has been visibly reduced",
        evidence=EvidenceReference(media_id=media_id, claim_ids=["e1"],
            original_image_reviewed=True, independent_review_passed=True),
        confirmation_required=confirmed, estimate_min=10, estimate_max=25,
        estimate_rationale="Two published independent task-duration references",
        estimate_sources=["https://sample.test/a"])


def verdict(task_id, media, condition, percent=None, next_step=None):
    return ReviewedOutcome(task_id=task_id, verdict=condition,
        evidence=EvidenceReference(media_id=media, claim_ids=["fresh-1"],
            original_image_reviewed=True, independent_review_passed=True),
        criterion_verified=condition == OutcomeVerdict.completed,
        reviewer_explanation="The new photograph shows an independently reviewed change to the closet floor",
        progress_percent=percent, next_step=next_step)


def test_tasks_create_durable_suggestions_without_acceptance(service):
    task_id = service.discover("home", room(), [action()])["created"][0]
    found = service.alerts("home")
    assert len(found) == 1 and found[0]["kind"] == "suggestion"
    assert len(service.alerts("other-household")) == 0
    assert service.list_tasks("home")[0]["status"] == "pending"
    assert service.decide("home", task_id, "done")["status"] == "in_progress"
    assert service.list_tasks("home")[0]["status"] != "completed"
    assert service.read_alert("home", found[0]["id"])["read_at"]
    assert len([a for a in service.alerts("home") if a["read_at"] is None]) == 0
    with pytest.raises(LookupError):
        service.read_alert("other-household", found[0]["id"])


def test_high_risk_action_keeps_approval_gate(service):
    service.discover("home", room(), [action(confirmed=True)])
    assert service.alerts("home") == []
    assert service.list_tasks("home")[0]["status"] == "proposed"


def test_partial_progress_updates_are_durable_and_evidence_linked(service):
    task_id = service.discover("home", room(), [action()])["created"][0]
    result = service.verify_fresh_scene("home", room(), [verdict(
        task_id, "photo-2", OutcomeVerdict.partially_completed, 20,
        "Sort the remaining items near the shelving")])
    assert result[task_id] == "progress_updated"
    task = service.list_tasks("home")[0]
    assert task["status"] == "in_progress" and task["progress"]["percent"] == 20
    assert task["progress"]["next_step"].startswith("Sort")
    assert any(a["kind"] == "progress" for a in service.alerts("home"))

    alert_count = len(service.alerts("home"))
    assert service.verify_fresh_scene("home", room(), [verdict(
        task_id, "photo-2", OutcomeVerdict.partially_completed, 20)])[task_id] == "already_reviewed"
    assert len(service.alerts("home")) == alert_count
    service.verify_fresh_scene("home", room(), [verdict(
        task_id, "photo-3", OutcomeVerdict.partially_completed, 60)])
    assert service.list_tasks("home")[0]["progress"]["percent"] == 60
    service.verify_fresh_scene("home", room(), [verdict(
        task_id, "photo-4", OutcomeVerdict.completed, 100)])
    assert service.list_tasks("home")[0]["progress"]["percent"] == 100
    assert service.list_tasks("home")[0]["status"] == "completed"
    assert any(a["kind"] == "completed" for a in service.alerts("home"))


def test_unverified_view_preserves_previous_progress(service):
    task_id = service.discover("home", room(), [action()])["created"][0]
    service.verify_fresh_scene("home", room(), [verdict(
        task_id, "second", OutcomeVerdict.partially_completed, 20)])
    assert service.verify_fresh_scene("home", room("other"), [verdict(
        task_id, "third", OutcomeVerdict.completed, 100)])[task_id] == "unmatched_task_or_room"
    assert service.verify_fresh_scene("home", room(), [verdict(
        task_id, "third", OutcomeVerdict.inconclusive)])[task_id] == "kept_active"
    assert service.list_tasks("home")[0]["progress"]["percent"] == 20


def test_partial_progress_needs_evidence_supported_percent():
    with pytest.raises(ValueError, match="Partial progress"):
        verdict("task", "second", OutcomeVerdict.partially_completed, None)
    with pytest.raises(ValueError, match="Inconclusive"):
        verdict("task", "second", OutcomeVerdict.inconclusive, 30)


def test_time_preferences_only_schedule_if_duration_fits_and_day_matches(service):
    profile = service.set_availability("home", timezone_name="America/Phoenix",
        start_time="18:00", end_time="19:00", weekdays=[0, 1, 2, 3, 4])
    assert profile["weekdays"] == [0, 1, 2, 3, 4]
    service.discover("home", room(), [action()])
    assert service.list_tasks("home")[0]["recommended_at"]
    example_clock = datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc)
    suggested = recommended_window(profile, 25, clock=example_clock)
    assert suggested is not None
    assert recommended_window(profile, 150, clock=example_clock) is None
    assert recommended_window(None, 25, clock=example_clock) is None
    assert recommended_window(profile, None, clock=example_clock) is None
    with pytest.raises(ValueError, match="start before"):
        service.set_availability("home", timezone_name="UTC", start_time="21:00", end_time="18:00", weekdays=[0])
    assert service.get_availability("other-household") is None


def test_same_task_is_not_reannounced_on_repeat_scan(service):
    service.discover("home", room(), [action()])
    service.discover("home", room(), [action(media_id="photo-2")])
    assert len(service.alerts("home")) == 1

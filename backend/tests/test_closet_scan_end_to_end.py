from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService
from app.services.autonomous_lifecycle import AutonomousLifecycle
from app.services.autonomous_scan_bridge import AutonomousScanBridge
from app.services.open_world_live import (
    OpenWorldActionReviewer, OpenWorldPlanner, OpenWorldVision,
)
from app.vision.autonomous_api import run_autonomous_scan

ACTION = {"action_id": "a1", "title": "Sort the scattered clothes",
          "action": "Pick up the clothes lying on the closet floor and sort them into piles",
          "observation_location": "closet floor", "action_location": "closet",
          "supporting_evidence_ids": ["e1"], "prerequisites": [], "assumptions": [],
          "verification_criteria": "The closet floor is visible and free of loose clothing",
          "estimated_effort": {"minimum_minutes": 20, "maximum_minutes": 40,
                               "rationale": "Floor and shelf clutter are visible",
                               "evidence_ids": ["e1", "e2"]},
          "requires_user_confirmation": False, "hazard_or_professional_help": False}

REVIEW = {"action_id": "a1", "directly_supported": True, "feasible": True,
          "no_unsupported_assumptions": True, "safety_appropriate": True,
          "necessary_or_useful": True, "proportionate": True, "nonredundant": True,
          "intent_and_state_respected": True,
          "explanation": "Clothes cover the closet floor and tidying is proportionate"}


class Primary:
    model = "scripted"

    def ask(self, *, instruction, payload=None, **_):
        if payload is None:
            return {"room_category": "Laundry Room", "claims": [
                {"id": "e1", "description": "Clothes are scattered across the closet floor"},
                {"id": "e2", "description": "Hanging rails and built-in shelves hold clothing"}]}
        return {"actions": [ACTION]}


class Reviewer:
    def __init__(self, label):
        self.label, self.client = label, SimpleNamespace(close=lambda: None)

    def ask(self, *, instruction, payload=None, **_):
        if "necessity-and-safety" in instruction:
            return {"reviews": [REVIEW]}
        return {"room_supported": False, "room_category": self.label,
                "claims": [{"id": "e1", "supported": True}, {"id": "e2", "supported": True}]}


def pipeline():
    primary = Primary()
    vision = OpenWorldVision(primary, Reviewer("Walk-in closet"), Reviewer("closet"))
    return vision, OpenWorldPlanner(primary), OpenWorldActionReviewer(Reviewer("unused"))


def make_services():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    media = SimpleNamespace(get_image=lambda *_: (SimpleNamespace(content_type="image/jpeg"), b"closet-photo"))
    return AutonomousJobService(sessions), AutonomousScanBridge(AutonomousLifecycle(sessions)), media


def run_worker(jobs, bridge, media):
    with patch('app.services.effort_research.ground_action_effort', side_effect=lambda action: action.model_copy(update={'estimated_effort': None})):
        return jobs.process_one(media=media, bridge=bridge, build_pipeline=pipeline, scan=run_autonomous_scan)


def test_cluttered_closet_yields_one_justified_task_in_the_corrected_room():
    jobs, bridge, media = make_services()
    jobs.enqueue("home", "closet-1")
    assert run_worker(jobs, bridge, media) == "completed"

    room = jobs.rooms("home")[0]
    assert room["room_category"] == "Walk-in closet"

    [task] = bridge.get_tasks("home")
    assert task["title"] == "Sort the scattered clothes"
    assert task["room_id"] == room["room_id"] and task["status"] == "pending"
    assert task["effort_min"] is None and task["created_at"]
    assert "scattered across the closet floor" in task["evidence_summary"]

    summary = jobs.jobs("home")[0]["review_summary"]
    assert summary["proposed_count"] == 1 and summary["approved_count"] == 1 and summary["created_count"] == 1


def test_recheck_of_the_same_photo_does_not_duplicate_the_task():
    jobs, bridge, media = make_services()
    jobs.enqueue("home", "closet-1")
    run_worker(jobs, bridge, media)
    jobs.recheck_completed("home", "closet-1")
    assert run_worker(jobs, bridge, media) == "completed"
    assert len(bridge.get_tasks("home")) == 1
    assert jobs.jobs("home")[0]["review_summary"]["existing_count"] == 1


def test_done_report_is_not_proof_and_needs_no_acceptance_for_ordinary_work():
    jobs, bridge, media = make_services()
    jobs.enqueue("home", "closet-1")
    run_worker(jobs, bridge, media)
    task_id = bridge.get_tasks("home")[0]["id"]
    bridge.lifecycle.decide("home", task_id, "done")
    assert bridge.get_tasks("home")[0]["status"] == "in_progress"
    assert bridge.get_tasks("home")[0]["progress"] is None

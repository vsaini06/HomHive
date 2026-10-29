"""Conservative connector between independently verified scene results and task lifecycle.

This module performs no LLM calls or physical-room guessing. The caller must
provide authenticated household scope, independently checked room continuity,
and independently reviewed action/outcome results. It never writes in preview.
"""
from __future__ import annotations

from typing import Protocol
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .autonomous_lifecycle import (
    AutonomousLifecycle, EvidenceReference, RoomContinuity,
    ReviewedOutcome, VerifiedAction,
)
from .open_world_planning import ActionProposal, Evidence, stable_action_key


class VerifiedScan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: str = Field(min_length=1)
    corroborated_evidence: list[Evidence]
    approved_actions: list[ActionProposal]
    independently_reviewed: bool
    original_media_reviewed: bool
    room: RoomContinuity
    room_category: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def check_evidence(self):
        if not self.independently_reviewed or not self.original_media_reviewed:
            raise ValueError("Independent original-media review is required")
        ids = {e.id for e in self.corroborated_evidence}
        if len(ids) != len(self.corroborated_evidence):
            raise ValueError("Duplicate corroborated evidence IDs")
        if any(e.source_id != self.media_id for e in self.corroborated_evidence):
            raise ValueError("Corroborated claims must refer to this scan")
        if any(e.provenance != "visible" for e in self.corroborated_evidence):
            raise ValueError("This image integration accepts visible evidence only")
        if any(not set(a.supporting_evidence_ids).issubset(ids)
               or not a.supporting_evidence_ids for a in self.approved_actions):
            raise ValueError("Action cites evidence absent from the verified scan")
        return self


class ScanOutcomeReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: str = Field(min_length=1)
    room: RoomContinuity
    corroborated_evidence: list[Evidence]
    outcomes: list[ReviewedOutcome]

    @model_validator(mode="after")
    def check_provenance(self):
        ids = {e.id for e in self.corroborated_evidence}
        if len(ids) != len(self.corroborated_evidence):
            raise ValueError("Duplicate observation claims")
        if any(e.provenance != "visible" or e.source_id != self.media_id
               for e in self.corroborated_evidence):
            raise ValueError("Unverified image provenance")
        if len({o.task_id for o in self.outcomes}) != len(self.outcomes):
            raise ValueError("Duplicate completion verdicts")
        for outcome in self.outcomes:
            if outcome.evidence.media_id != self.media_id:
                raise ValueError("Completion review references a different photograph")
            if not set(outcome.evidence.claim_ids).issubset(ids):
                raise ValueError("Completion verdict must reference corroborated fresh observations")
        return self


def to_verified_action(action: ActionProposal, scan: VerifiedScan) -> VerifiedAction:
    """Preserve review-required confirmation and uncertainty, never invent effort."""
    estimate = action.estimated_effort
    return VerifiedAction(
        action_key=stable_action_key(action), title=action.title, action=action.action,
        observed_location=action.observation_location,
        room_category=scan.room_category,
        evidence_summary=" ".join(item.description for item in scan.corroborated_evidence
                                  if item.id in action.supporting_evidence_ids)[:800] or None,
        action_location=action.action_location,
        verification_criteria=action.verification_criteria,
        evidence=EvidenceReference(
            media_id=scan.media_id, claim_ids=action.supporting_evidence_ids,
            original_image_reviewed=True, independent_review_passed=True,
        ),
        estimate_min=estimate.minimum_minutes if estimate else None,
        estimate_max=estimate.maximum_minutes if estimate else None,
        estimate_rationale=estimate.rationale if estimate else None,
        estimate_sources=list(estimate.source_urls) if estimate and estimate.externally_verified and len(estimate.source_urls) >= 2 else [],
        confirmation_required=action.requires_user_confirmation or action.hazard_or_professional_help,
    )


class AutonomousScanBridge:
    """Only call following an authenticated household membership check.

    The independent vision/planning pipeline must run *before* VerifiedScan is
    constructed. RoomContinuity must come from a trusted room registry + independent
    matching, never from the planning model's room category.
    """
    def __init__(self, lifecycle: AutonomousLifecycle):
        self.lifecycle = lifecycle

    def persist_verified_scan(self, household_id: str, scan: VerifiedScan) -> dict:
        actions = [to_verified_action(a, scan) for a in scan.approved_actions]
        return self.lifecycle.discover(household_id, scan.room, actions)

    def reconcile_verified_scan(self, household_id: str, review: ScanOutcomeReview) -> dict:
        return self.lifecycle.verify_fresh_scene(household_id, review.room, review.outcomes)

    def get_tasks(self, household_id: str) -> list[dict]:
        return self.lifecycle.list_tasks(household_id)

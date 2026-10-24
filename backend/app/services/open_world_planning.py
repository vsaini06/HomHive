"""Evidence-grounded, open-vocabulary household task proposals.

No room/task taxonomy is imposed. Model-proposed actions must pass a separate
review and deterministic invariants before they may be persisted. This module
is deliberately provider-agnostic; callers supply two independently obtained
responses, each grounded in the original media/evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=5, max_length=800)
    provenance: Literal["visible", "user_confirmed", "trusted_history", "external_research"]
    source_id: str = Field(min_length=1, max_length=128)


class SceneContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str | None = Field(default=None, max_length=120)
    category_supported: bool = False
    physical_room_id: str | None = None
    physical_room_confirmed: bool = False

    @model_validator(mode="after")
    def room_invariants(self):
        if self.physical_room_id and not self.physical_room_confirmed:
            raise ValueError("Physical room identity requires explicit independent confirmation")
        if self.category and not self.category_supported:
            raise ValueError("Unsupported room category must not be asserted")
        return self


class EffortEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minimum_minutes: int = Field(ge=1, le=10080)
    maximum_minutes: int = Field(ge=1, le=10080)
    rationale: str = Field(min_length=12, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    externally_verified: bool = False

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum_minutes > self.maximum_minutes:
            raise ValueError("Effort range reversed")
        return self


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=4, max_length=180)
    action: str = Field(min_length=8, max_length=1000)
    observation_location: str | None = Field(default=None, max_length=180)
    action_location: str | None = Field(default=None, max_length=180)
    supporting_evidence_ids: list[str] = Field(min_length=1, max_length=12)
    prerequisites: list[str] = Field(default_factory=list, max_length=12)
    assumptions: list[str] = Field(default_factory=list, max_length=12)
    verification_criteria: str = Field(min_length=12, max_length=600)
    estimated_effort: EffortEstimate | None = None
    requires_user_confirmation: bool = False
    hazard_or_professional_help: bool = False


class ProposedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene: SceneContext
    evidence: list[Evidence] = Field(max_length=50)
    actions: list[ActionProposal] = Field(max_length=20)


class ActionReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str
    directly_supported: bool
    feasible: bool
    no_unsupported_assumptions: bool
    safety_appropriate: bool
    explanation: str = Field(min_length=4, max_length=400)


class IndependentPlanReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviews: list[ActionReview] = Field(max_length=20)


class ReviewOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: list[ActionProposal]
    rejected: dict[str, str]


def evaluate_proposals(plan: ProposedPlan, review: IndependentPlanReview,
                       existing_active_keys: set[str] | None = None) -> ReviewOutcome:
    """Fail closed on missing evidence, malformed/duplicate review, or unsafe assumptions."""
    seen = set()
    evidence = {e.id: e for e in plan.evidence}
    if len(evidence) != len(plan.evidence):
        raise ValueError("Evidence identifiers must be unique")
    review_by_id = {r.action_id: r for r in review.reviews}
    if len(review_by_id) != len(review.reviews):
        raise ValueError("Duplicate reviewer action identifiers")
    proposed_ids = {a.action_id for a in plan.actions}
    if not set(review_by_id).issubset(proposed_ids):
        raise ValueError("Reviewer must account for every proposed action and no others")
    keys = set(existing_active_keys or ())
    approved, rejected = [], {}
    for action in plan.actions:
        if action.action_id in seen:
            raise ValueError("Duplicate proposed action identifiers")
        seen.add(action.action_id)
        cited = set(action.supporting_evidence_ids)
        estimate_ids = set(action.estimated_effort.evidence_ids) if action.estimated_effort else set()
        if len(cited) != len(action.supporting_evidence_ids) or not cited.issubset(evidence):
            rejected[action.action_id] = "missing_or_duplicate_evidence"
            continue
        if action.estimated_effort and estimate_ids.issubset(evidence) and not estimate_ids.issubset(cited):
            rejected[action.action_id] = "effort_not_supported_by_action_evidence"
            continue
        if estimate_ids and not estimate_ids.issubset(evidence):
            rejected[action.action_id] = "unsupported_effort_estimate"
            continue
        r = review_by_id.get(action.action_id)
        if r is None or not all((r.directly_supported, r.feasible,
                                 r.no_unsupported_assumptions, r.safety_appropriate)):
            rejected[action.action_id] = "independent_review_rejected_or_missing"
            continue
        if action.hazard_or_professional_help and not action.requires_user_confirmation:
            rejected[action.action_id] = "safety_confirmation_required"
            continue
        key = stable_action_key(action)
        if key in keys:
            rejected[action.action_id] = "duplicate_active_action"
            continue
        keys.add(key)
        approved.append(action)
    return ReviewOutcome(approved=approved, rejected=rejected)


def stable_action_key(action: ActionProposal) -> str:
    """Content-address the meaningful action and target, not the scan/media identifier."""
    def normalize(value: str | None) -> str:
        return re.sub(r"\s+", " ", (value or "unknown").strip().lower())
    data = [normalize(action.action), normalize(action.action_location),
            normalize(action.observation_location)]
    return "open_world:" + hashlib.sha256(json.dumps(data).encode()).hexdigest()[:24]


PLANNER_INSTRUCTIONS = """You are a household action planner. Use the provided, independently
corroborated scene evidence and known household history, not assumptions. Output JSON matching
ProposedPlan. There is NO closed room, object, condition, or task taxonomy: name unfamiliar
things accurately when visible. Separate an observable condition from a proposed action,
the observation location from where work occurs, and room CATEGORY from exact room ID.
Do not infer that clothes need washing just because clothes are on the floor. Propose
sorting/folding where visible evidence supports that; make washing conditional on evidence.
Generate zero actions when nothing needs doing. Cite exact supplied evidence IDs for each
action. Don't invent prices, tools, durations, brand/model identifiers, room IDs, or
historical facts. Use a duration RANGE with rationale when evidence permits it; omit
an estimate otherwise. For unfamiliar objects or repair procedures, require research or
human confirmation. Hazards must be marked for confirmation/professional handling.
Descriptions should say what to do and where, with verifiable completion criteria.
"""

REVIEWER_INSTRUCTIONS = """Independently assess EACH proposed action against the ORIGINAL
evidence and image, not merely the planning model's assertions. Return IndependentPlanReview
with exactly one review per action. Mark directly_supported=false for guesses (e.g. laundry
needing washing when clean/dirty status is unknown), unsupported room identity, or missing
objects. Mark safety_appropriate=false for risky or unjustified instructions. Fail closed.
"""

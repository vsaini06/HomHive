"""Provider-independent orchestration for open-world, independently reviewed plans.

This is an explicit service boundary, not a live HTTP handler. Callers must pass
corroborated evidence obtained independently from the planner and the original
media reviewer. Never accept planner-generated evidence as trusted ground truth.
"""
from __future__ import annotations
from typing import Protocol
from pydantic import BaseModel, ConfigDict, Field
from .open_world_planning import (
    Evidence, SceneContext, ProposedPlan, IndependentPlanReview,
    ReviewOutcome, evaluate_proposals, stable_action_key,
)


class Planner(Protocol):
    def propose(self, evidence: list[Evidence], scene: SceneContext) -> ProposedPlan: ...


class PlanReviewer(Protocol):
    def review(self, plan: ProposedPlan, original_media: bytes, media_type: str) -> IndependentPlanReview: ...


class PlanningResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: ReviewOutcome
    proposed_count: int = Field(ge=0)
    accepted_keys: list[str]


def plan_verified_scene(*, corroborated_evidence: list[Evidence],
                        independently_supported_scene: SceneContext,
                        original_media: bytes, media_type: str,
                        planner: Planner, reviewer: PlanReviewer,
                        active_task_keys: set[str] | None = None) -> PlanningResult:
    """Fail closed. Both model callbacks are mandatory and receive distinct input.

    The review must use the original image. The planner may supply recommendations,
    never extra observations or a different room identity. Nothing is persisted here.
    """
    if not original_media or not media_type.startswith(("image/", "video/")):
        raise ValueError("Original image or video is required for review")
    if not corroborated_evidence:
        return PlanningResult(
            outcome=ReviewOutcome(approved=[], rejected={}), proposed_count=0,
            accepted_keys=[])
    ids = {item.id for item in corroborated_evidence}
    if len(ids) != len(corroborated_evidence):
        raise ValueError("Corroborated evidence IDs must be unique")
    proposal = planner.propose(corroborated_evidence, independently_supported_scene)
    # An LLM cannot authoritatively add evidence, rewrite source IDs, or turn an
    # unverified room into a supported category merely by asserting it.
    if proposal.evidence != corroborated_evidence or proposal.scene != independently_supported_scene:
        raise ValueError("Planner altered corroborated evidence or room provenance")
    independent_review = reviewer.review(proposal, original_media, media_type)
    outcome = evaluate_proposals(proposal, independent_review, active_task_keys)
    return PlanningResult(
        outcome=outcome, proposed_count=len(proposal.actions),
        accepted_keys=[stable_action_key(item) for item in outcome.approved],
    )

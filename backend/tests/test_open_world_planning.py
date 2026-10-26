from app.services.open_world_planning import (
    ActionProposal, ActionReview, Evidence, EffortEstimate, IndependentPlanReview,
    ProposedPlan, SceneContext, evaluate_proposals, stable_action_key,
)
import pytest
from pydantic import ValidationError


def base():
    plan = ProposedPlan(
        scene=SceneContext(category="walk-in closet", category_supported=True),
        evidence=[Evidence(id="e1", description="Clothing is piled on the closet floor", provenance="visible", source_id="photo1")],
        actions=[ActionProposal(action_id="a1", title="Sort clothing", action="Sort and fold clothing scattered on the floor", observation_location="walk-in closet", action_location="walk-in closet", supporting_evidence_ids=["e1"], verification_criteria="Clothing cleared from floor and put away")],
    )
    review = IndependentPlanReview(reviews=[ActionReview(action_id="a1", directly_supported=True, feasible=True, no_unsupported_assumptions=True, safety_appropriate=True, explanation="Clutter is clearly visible")])
    return plan, review


def test_supported_open_vocab_closet_action():
    p,r=base(); result=evaluate_proposals(p,r)
    assert len(result.approved)==1
    assert p.scene.category=="walk-in closet"


def test_dirty_laundry_inference_rejected():
    p,r=base(); p.actions[0].action="Wash all the dirty clothes in the laundry room"
    r.reviews[0].directly_supported=False
    assert not evaluate_proposals(p,r).approved


def test_unverified_room_identity_rejected():
    with pytest.raises(ValidationError):
        SceneContext(category="closet", category_supported=True, physical_room_id="upstairs-closet")


def test_unknown_room_category_is_allowed():
    assert SceneContext().category is None


def test_missing_independent_review_fails_closed():
    p,_=base()
    assert evaluate_proposals(p,IndependentPlanReview(reviews=[])).rejected["a1"]


def test_unrelated_evidence_cannot_be_cited():
    p,r=base(); p.actions[0].supporting_evidence_ids=["invented"]
    assert evaluate_proposals(p,r).rejected["a1"]=="missing_or_duplicate_evidence"


def test_ungrounded_effort_is_dropped_without_rejecting_a_supported_action():
    p,r=base(); p.actions[0].estimated_effort=EffortEstimate(minimum_minutes=10,maximum_minutes=25,rationale="Visible pile suggests several pieces",evidence_ids=["invented"])
    outcome=evaluate_proposals(p,r)
    assert not outcome.rejected and outcome.approved[0].estimated_effort is None


def test_duplicate_work_is_blocked_across_images():
    p,r=base(); key=stable_action_key(p.actions[0]); assert not evaluate_proposals(p,r,{key}).approved


def test_danger_requires_explicit_confirmation():
    p,r=base(); p.actions[0].hazard_or_professional_help=True
    assert evaluate_proposals(p,r).rejected["a1"]=="safety_confirmation_required"


def test_two_actions_cannot_use_same_id():
    p,r=base(); p.actions.append(p.actions[0].model_copy())
    with pytest.raises(ValueError):
        evaluate_proposals(p,r)

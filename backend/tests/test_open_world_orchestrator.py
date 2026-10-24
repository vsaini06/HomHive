import pytest
from app.services.open_world_planning import (
    Evidence, SceneContext, ProposedPlan, ActionProposal,
    ActionReview, IndependentPlanReview,
)
from app.services.open_world_orchestrator import plan_verified_scene

EVIDENCE = [Evidence(id="e1", description="Garments are scattered across the floor", provenance="visible", source_id="scan_1")]
SCENE = SceneContext(category="walk-in closet", category_supported=True)
ACTION = ActionProposal(action_id="a1", title="Organize clothes", action="Fold and hang the clothes in the closet", observation_location="walk-in closet", action_location="walk-in closet", supporting_evidence_ids=["e1"], verification_criteria="The floor is cleared and garments are stored")

class Planner:
    def __init__(self, altered=False): self.altered=altered
    def propose(self, evidence, scene):
        if self.altered: scene=SceneContext(category="laundry room", category_supported=True)
        return ProposedPlan(evidence=evidence, scene=scene, actions=[ACTION])

class Reviewer:
    def __init__(self, supported=True): self.supported=supported; self.seen=None
    def review(self, plan, original_media, media_type):
        self.seen=(original_media,media_type)
        return IndependentPlanReview(reviews=[ActionReview(action_id="a1", directly_supported=self.supported, feasible=True, no_unsupported_assumptions=True, safety_appropriate=True, explanation="Directly visible clutter")])

def run(planner=None,reviewer=None,keys=None):
    return plan_verified_scene(corroborated_evidence=EVIDENCE, independently_supported_scene=SCENE, original_media=b"media", media_type="image/jpeg", planner=planner or Planner(), reviewer=reviewer or Reviewer(), active_task_keys=keys)

def test_approved_open_world_action():
    reviewer=Reviewer(); result=run(reviewer=reviewer)
    assert len(result.outcome.approved)==1
    assert result.proposed_count==1 and reviewer.seen==(b"media","image/jpeg")

def test_fails_closed_when_rejected():
    result=run(reviewer=Reviewer(False)); assert not result.outcome.approved

def test_blocks_planner_room_rewrite():
    with pytest.raises(ValueError,match="altered"): run(planner=Planner(altered=True))

def test_blocks_duplicate_active_work():
    key=run().accepted_keys[0]
    assert not run(keys={key}).outcome.approved

def test_refuses_missing_original_media():
    with pytest.raises(ValueError):
        plan_verified_scene(corroborated_evidence=EVIDENCE, independently_supported_scene=SCENE, original_media=b"", media_type="image/jpeg", planner=Planner(), reviewer=Reviewer())

def test_no_evidence_no_llm_calls():
    assert plan_verified_scene(corroborated_evidence=[], independently_supported_scene=SCENE, original_media=b"x",media_type="image/png",planner=None,reviewer=None).proposed_count==0

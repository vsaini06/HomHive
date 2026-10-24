import pytest
from app.services.open_world_live import (VisualClaim, VisualScene, ClaimVerdict,
    VisualReview, corroborate_scene, preview_verified_scene)
from app.services.open_world_planning import (ActionProposal, ActionReview, IndependentPlanReview, ProposedPlan)


class Vision:
    def __init__(self, supported=True): self.supported=supported
    def extract(self, image, media_type):
        return VisualScene(room_category="laundry room", claims=[VisualClaim(id="e1", description="Clothing piles on and around the washer")])
    def verify(self, scene, image, media_type):
        assert image == b"photo"
        return VisualReview(room_supported=True, claims=[ClaimVerdict(id="e1", supported=self.supported)])


class Planner:
    def __init__(self): self.calls=0
    def propose(self, evidence, scene):
        self.calls+=1
        return ProposedPlan(scene=scene,evidence=evidence,actions=[ActionProposal(action_id="a1",title="Organize clothing",
            action="Sort the visible piles of clothing", observation_location="laundry room", action_location="laundry room",
            supporting_evidence_ids=["e1"],verification_criteria="Laundry floor and machine tops cleared")])


class Reviewer:
    def review(self, plan, original_media, media_type):
        assert original_media==b"photo"
        return IndependentPlanReview(reviews=[ActionReview(action_id="a1",directly_supported=True,
            feasible=True,no_unsupported_assumptions=True,safety_appropriate=True,explanation="Visual clutter")])


def test_end_to_end_preview_uses_only_verified_evidence_and_never_persists():
    result=preview_verified_scene(image=b"photo",media_type="image/jpeg",media_id="m1",vision=Vision(),planner=Planner(),reviewer=Reviewer())
    assert result.room_category=="laundry room"
    assert [e.description for e in result.corroborated_evidence]==["Clothing piles on and around the washer"]
    assert result.approved_actions[0]["estimated_effort"] is None
    assert result.saved is False


def test_disputed_visual_claim_does_not_reach_planner():
    p=Planner()
    result=preview_verified_scene(image=b"photo",media_type="image/jpeg",media_id="m1",vision=Vision(False),planner=p,reviewer=Reviewer())
    assert not result.approved_actions and not result.corroborated_evidence
    assert p.calls==0 and result.verification=="no_corroborated_evidence"


def test_review_must_address_every_claim_without_duplicates():
    s=VisualScene(claims=[VisualClaim(id="e1",description="Piles of laundry visible")])
    with pytest.raises(ValueError):corroborate_scene(s,VisualReview(room_supported=False,claims=[]),"m1")
    with pytest.raises(ValueError):corroborate_scene(s,VisualReview(room_supported=False,
        claims=[ClaimVerdict(id="e1",supported=True),ClaimVerdict(id="e1",supported=True)]),"m1")


def test_unverified_room_category_is_omitted():
    s=VisualScene(room_category="walk-in closet",claims=[VisualClaim(id="e1",description="Clothing scattered across floor")])
    scene,evidence=corroborate_scene(s,VisualReview(room_supported=False,claims=[ClaimVerdict(id="e1",supported=True)]),"m1")
    assert scene.category is None and len(evidence)==1


def test_unknown_input_is_refused():
    with pytest.raises(ValueError):preview_verified_scene(image=b"",media_type="image/jpeg",media_id="m",vision=None,planner=None,reviewer=None)


def test_parser_does_not_scavenge_prose():
    from app.services.open_world_live import _read_json_text
    with pytest.raises(Exception): _read_json_text('Here is the answer: {"claims":[]}')
    assert _read_json_text('```json\n{"claims": []}\n```')=={"claims":[]}

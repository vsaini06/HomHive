import pytest
from pydantic import ValidationError

from app.services.open_world_live import (
    NecessityReview, StrictIndependentReview, gate_action_necessity, OpenWorldActionReviewer,
)
from app.services.open_world_planning import (
    SceneContext, Evidence, ActionProposal, ProposedPlan, evaluate_proposals,
)


def plan():
    return ProposedPlan(
        scene=SceneContext(category="laundry room", category_supported=True),
        evidence=[Evidence(id="e1", description="Washing machine lid visibly open", provenance="visible", source_id="photo")],
        actions=[ActionProposal(action_id="a1", title="Close machine lid", action="Close lid on washer without checking its state", supporting_evidence_ids=["e1"], verification_criteria="Lid is closed and items cleared")],
    )


def response(**overrides):
    values = dict(action_id="a1", directly_supported=True, feasible=True,
                  no_unsupported_assumptions=True, safety_appropriate=True,
                  necessary_or_useful=True, proportionate=True, nonredundant=True,
                  intent_and_state_respected=True,
                  explanation="The action is evidenced and clearly useful")
    values.update(overrides)
    return StrictIndependentReview(reviews=[NecessityReview(**values)])


@pytest.mark.parametrize("gate", [
    "necessary_or_useful", "proportionate", "nonredundant", "intent_and_state_respected",
    "directly_supported", "feasible", "no_unsupported_assumptions", "safety_appropriate",
])
def test_any_failed_gate_rejects_action(gate):
    p = plan()
    review = gate_action_necessity(p, response(**{gate: False}))
    assert not evaluate_proposals(p, review).approved


def test_all_gates_true_allows_valid_action():
    p = plan()
    assert len(evaluate_proposals(p, gate_action_necessity(p, response())).approved) == 1


def test_missing_necessity_field_fails_closed():
    values = response().model_dump()["reviews"][0]
    values.pop("necessary_or_useful")
    with pytest.raises(ValidationError):
        StrictIndependentReview.model_validate({"reviews": [values]})


def test_duplicate_or_missing_reviews_rejected():
    p = plan()
    with pytest.raises(ValueError):
        gate_action_necessity(p, StrictIndependentReview(reviews=[]))
    r = response().reviews[0]
    with pytest.raises(ValueError):
        gate_action_necessity(p, StrictIndependentReview(reviews=[r, r]))


def test_model_adapter_uses_strict_necessity_gates():
    class StubClient:
        def ask(self, **kwargs):
            assert "necessary_or_useful" in kwargs["instruction"]
            assert kwargs["image"] == b"photo"
            return response(necessary_or_useful=False).model_dump()
    p = plan()
    result = OpenWorldActionReviewer(StubClient()).review(p, b"photo", "image/jpeg")
    assert evaluate_proposals(p, result).rejected["a1"]


def test_intent_neutral_suggestion_is_reviewed_as_optional_not_mandatory():
    from app.services.open_world_live import OpenWorldPlanner
    from app.services.open_world_planning import SceneContext, Evidence, evaluate_proposals

    evidence = [Evidence(id="e1", description="Clothes are scattered across the closet floor",
                         provenance="visible", source_id="closet-photo")]
    scene = SceneContext(category="closet", category_supported=True)

    class IntentAwarePlannerClient:
        def ask(self, *, instruction, payload=None, **kwargs):
            assert "intent-neutral" in instruction
            assert "requires_user_confirmation=true" in instruction
            assert "optional" in instruction
            return {"actions": [{
                "action_id": "a1", "title": "Check and sort loose clothing",
                "action": "Check if clothes on the closet floor are staged intentionally; "
                          "if not, sort them according to the owner's preferences",
                "observation_location": "closet floor", "action_location": "closet floor",
                "supporting_evidence_ids": ["e1"], "prerequisites": [], "assumptions": [],
                "verification_criteria": "User confirms the placement is intentional or "
                                         "the floor is visibly clear of loose clothing",
                "estimated_effort": None, "requires_user_confirmation": True,
                "hazard_or_professional_help": False,
            }]}

    class IndependentReviewerClient:
        def ask(self, *, instruction, payload=None, image=None, **kwargs):
            assert "necessary_or_useful is true" in instruction
            assert "Do not reject such an action ONLY because" in instruction
            assert image == b"closet-image"
            return {"reviews": [{
                "action_id": "a1", "directly_supported": True, "feasible": True,
                "no_unsupported_assumptions": True, "safety_appropriate": True,
                "necessary_or_useful": True, "proportionate": True,
                "nonredundant": True, "intent_and_state_respected": True,
                "explanation": "A conditional check is useful without assuming where the items belong",
            }]}

    proposal = OpenWorldPlanner(IntentAwarePlannerClient()).propose(evidence, scene)
    review = OpenWorldActionReviewer(IndependentReviewerClient()).review(proposal, b"closet-image", "image/jpeg")
    result = evaluate_proposals(proposal, review)
    assert len(result.approved) == 1
    assert not result.rejected
    assert result.approved[0].requires_user_confirmation is True
    assert result.approved[0].estimated_effort is None


def test_intent_neutral_prompt_does_not_override_independent_rejection():
    p = ProposedPlan(scene=SceneContext(category="closet", category_supported=True),
        evidence=[Evidence(id="e1", description="Clothes lie on the closet floor", provenance="visible", source_id="photo")],
        actions=[ActionProposal(action_id="a1", title="Put away every shirt",
            action="Put away all loose clothing in the closet without checking the owner's plans",
            supporting_evidence_ids=["e1"], verification_criteria="The closet floor has no loose shirts")])
    result = StrictIndependentReview(reviews=[NecessityReview(
        action_id="a1", directly_supported=True, feasible=True,
        no_unsupported_assumptions=False, safety_appropriate=True,
        necessary_or_useful=True, proportionate=True, nonredundant=True,
        intent_and_state_respected=False,
        explanation="No evidence that the clothing is ready to be put away")])
    outcome = evaluate_proposals(p, gate_action_necessity(p, result))
    assert outcome.approved == []
    assert "intent_or_state_presumed" in outcome.rejected["a1"]

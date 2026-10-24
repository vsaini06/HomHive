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

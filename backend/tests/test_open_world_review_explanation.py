from app.services.open_world_live import NecessityReview, StrictIndependentReview, gate_action_necessity
from app.services.open_world_planning import ActionProposal, Evidence, ProposedPlan, SceneContext
from pydantic import ValidationError
import pytest


def review(**updates):
    data = dict(action_id="a1", directly_supported=True, feasible=True,
                no_unsupported_assumptions=True, safety_appropriate=True,
                necessary_or_useful=True, proportionate=True, nonredundant=True,
                intent_and_state_respected=True, explanation="The observed condition merits attention")
    data.update(updates)
    return data


def plan():
    return ProposedPlan(scene=SceneContext(category="storage", category_supported=True),
        evidence=[Evidence(id="e1", description="Items obstruct the walking area", provenance="visible", source_id="img1")],
        actions=[ActionProposal(action_id="a1", title="Clear passage", action="Move obstructing items aside",
            supporting_evidence_ids=["e1"], verification_criteria="Walking area is accessible")])


def test_long_review_explanation_is_bounded_without_invalidating_review():
    outcome = StrictIndependentReview.model_validate({"reviews": [review(explanation="Evidence is sufficient. " * 60)]})
    assert len(outcome.reviews[0].explanation) <= 400
    assert gate_action_necessity(plan(), outcome).reviews[0].directly_supported


def test_long_explanation_does_not_change_negative_decision():
    outcome = StrictIndependentReview.model_validate({"reviews": [review(necessary_or_useful=False, explanation="This action is not necessary. " * 40)]})
    assert gate_action_necessity(plan(), outcome).reviews[0].directly_supported is False


def test_missing_gate_still_rejected():
    bad = review()
    bad.pop("intent_and_state_respected")
    with pytest.raises(ValidationError):
        StrictIndependentReview.model_validate({"reviews": [bad]})


def test_short_explanation_unchanged():
    text = "The visible obstruction needs clearing"
    assert NecessityReview.model_validate(review(explanation=text)).explanation == text


def test_non_string_explanation_still_rejected():
    with pytest.raises(ValidationError):
        NecessityReview.model_validate(review(explanation=["not text"]))

from types import SimpleNamespace

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.autonomous_jobs import AutonomousJobService
from app.services.open_world_live import (
    ClaimVerdict, OpenWorldPlanner, StrictIndependentReview, VisualClaim, VisualReview,
    VisualScene, categories_agree, corroborate_scene, gate_action_necessity,
)
from app.services.open_world_orchestrator import plan_verified_scene
from app.services.open_world_planning import (
    ActionProposal, ActionReview, EffortEstimate, Evidence, IndependentPlanReview,
    ProposedPlan, SceneContext, evaluate_proposals,
)

EVIDENCE = [
    Evidence(id="e1", description="Clothes scattered across the closet floor", provenance="visible", source_id="m1"),
    Evidence(id="e2", description="Shelves hold piled clothing", provenance="visible", source_id="m1"),
]


def action(**changes):
    values = dict(action_id="a1", title="Sort scattered clothes",
                  action="Pick up the clothes from the floor and sort them",
                  observation_location="closet floor", action_location="closet",
                  supporting_evidence_ids=["e1"],
                  verification_criteria="Closet floor is visible and clear of clothing")
    return ActionProposal(**{**values, **changes})


def approving_review(plan, original_media, media_type):
    return IndependentPlanReview(reviews=[ActionReview(
        action_id=a.action_id, directly_supported=True, feasible=True, no_unsupported_assumptions=True,
        safety_appropriate=True, explanation="Visible clutter justifies tidying") for a in plan.actions])


def test_effort_citing_other_valid_evidence_keeps_the_action_with_unknown_duration():
    effort = EffortEstimate(minimum_minutes=15, maximum_minutes=30,
                            rationale="Floor and shelf clutter are both visible", evidence_ids=["e1", "e2"])
    plan = ProposedPlan(scene=SceneContext(), evidence=EVIDENCE, actions=[action(estimated_effort=effort)])
    outcome = evaluate_proposals(plan, approving_review(plan, b"x", "image/jpeg"))
    assert outcome.rejected == {}
    assert outcome.approved[0].estimated_effort is None


def test_effort_fully_grounded_in_cited_evidence_is_preserved():
    effort = EffortEstimate(minimum_minutes=15, maximum_minutes=30,
                            rationale="Floor clutter is visible", evidence_ids=["e1"])
    plan = ProposedPlan(scene=SceneContext(), evidence=EVIDENCE, actions=[action(estimated_effort=effort)])
    outcome = evaluate_proposals(plan, approving_review(plan, b"x", "image/jpeg"))
    assert outcome.approved[0].estimated_effort.maximum_minutes == 30


class ScriptedClient:
    def __init__(self, *responses):
        self.responses, self.payloads = list(responses), []

    def ask(self, *, instruction, payload=None, **_):
        self.payloads.append(payload)
        return self.responses.pop(0)


ACTION_JSON = {"action_id": "a1", "title": "Sort scattered clothes",
               "action": "Pick up the clothes from the floor and sort them",
               "observation_location": "closet floor", "action_location": "closet",
               "supporting_evidence_ids": ["e1"], "prerequisites": [], "assumptions": [],
               "verification_criteria": "Closet floor is visible and clear of clothing",
               "estimated_effort": None, "requires_user_confirmation": False,
               "hazard_or_professional_help": False}


def test_planner_cannot_invalidate_a_plan_by_rewording_evidence():
    garbled = {"scene": {"category": "laundry room", "category_supported": True},
               "evidence": [{"id": "e1", "description": "reworded", "provenance": "visible", "source_id": "m1"}],
               "actions": [ACTION_JSON]}
    scene = SceneContext()
    planner = OpenWorldPlanner(ScriptedClient(garbled))
    result = plan_verified_scene(corroborated_evidence=EVIDENCE, independently_supported_scene=scene,
                                 original_media=b"x", media_type="image/jpeg", planner=planner,
                                 reviewer=SimpleNamespace(review=approving_review))
    assert [a.title for a in result.outcome.approved] == ["Sort scattered clothes"]


def test_planner_retries_schema_errors_then_surfaces_them():
    bad = {"actions": [{**ACTION_JSON, "estimated_effort": "45 minutes"}]}
    planner = OpenWorldPlanner(ScriptedClient(bad, bad))
    try:
        planner.propose(EVIDENCE, SceneContext())
    except ValidationError:
        pass
    else:
        raise AssertionError("invalid plans must not be coerced")


def test_planner_receives_existing_tasks_only_when_present():
    client = ScriptedClient({"actions": []}, {"actions": []})
    planner = OpenWorldPlanner(client)
    planner.propose(EVIDENCE, SceneContext())
    planner.propose(EVIDENCE, SceneContext(), existing_tasks=[{"title": "Sort clothes", "action": "Sort"}])
    assert "existing_tasks" not in client.payloads[0]
    assert client.payloads[1]["existing_tasks"][0]["title"] == "Sort clothes"


def test_rejection_names_the_failed_review_gates():
    plan = ProposedPlan(scene=SceneContext(), evidence=EVIDENCE, actions=[action()])
    strict = StrictIndependentReview.model_validate({"reviews": [dict(
        action_id="a1", directly_supported=True, feasible=True, no_unsupported_assumptions=True,
        safety_appropriate=True, necessary_or_useful=True, proportionate=True, nonredundant=True,
        intent_and_state_respected=False, explanation="Items could be stored this way on purpose")]})
    outcome = evaluate_proposals(plan, gate_action_necessity(plan, strict))
    assert outcome.rejected == {"a1": "independent_review_rejected:intent_or_state_presumed"}


def scene_with(category):
    return VisualScene(room_category=category, claims=[VisualClaim(id="e1", description="Clothes on the closet floor")])


def test_reviewer_disagreeing_about_category_leaves_it_uncertain_but_keeps_evidence():
    review = VisualReview(room_supported=True, room_category="walk-in closet",
                          claims=[ClaimVerdict(id="e1", supported=True)])
    context, evidence = corroborate_scene(scene_with("Laundry Room"), review, "m1")
    assert context.category is None and len(evidence) == 1


def test_reviewer_agreeing_about_category_confirms_it():
    review = VisualReview(room_supported=True, room_category="Closet",
                          claims=[ClaimVerdict(id="e1", supported=True)])
    context, _ = corroborate_scene(scene_with("Walk-in closet"), review, "m1")
    assert context.category == "Walk-in closet"


def test_category_agreement_ignores_generic_words_and_plurals():
    assert categories_agree("Walk-in Closet", "closets")
    assert not categories_agree("Laundry Room", "Walk-in Closet")
    assert categories_agree("Kitchen", None)


def test_failed_attempt_is_logged_without_payloads(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    jobs = AutonomousJobService(sessionmaker(engine, expire_on_commit=False))
    jobs.enqueue("h", "m")
    media = SimpleNamespace(get_image=lambda *_: (SimpleNamespace(content_type="image/jpeg"), b"image"))

    def failing_scan(**_):
        raise ValueError("Planner altered corroborated evidence or room provenance")

    records = []
    monkeypatch.setattr("app.services.autonomous_jobs.logger",
                        SimpleNamespace(warning=lambda message, *args: records.append(message % args)))
    assert jobs.process_one(media=media, bridge=None, build_pipeline=None, scan=failing_scan) == "retry_scheduled"
    assert "ValueError" in records[0] and "Planner altered" in records[0]
    assert jobs.jobs("h")[0]["state"] == "queued"


def test_reviewer_consensus_replaces_a_contradicted_category():
    review = VisualReview(room_supported=True, room_category="walk-in closet", category_by_reviewers=True,
                          claims=[ClaimVerdict(id="e1", supported=True)])
    context, evidence = corroborate_scene(scene_with("Laundry Room"), review, "m1")
    assert context.category == "walk-in closet" and len(evidence) == 1


def test_missing_actions_is_not_treated_as_a_valid_empty_plan():
    client = ScriptedClient({"reason": "cannot produce a plan"}, {"reason": "still not a plan"})
    with __import__("pytest").raises(ValueError, match="missing required actions"):
        OpenWorldPlanner(client).propose(EVIDENCE, SceneContext())
    assert len(client.payloads) == 2


def test_missing_actions_retries_and_uses_a_subsequent_valid_plan():
    client = ScriptedClient({"error": "incomplete"}, {"actions": [ACTION_JSON]})
    plan = OpenWorldPlanner(client).propose(EVIDENCE, SceneContext())
    assert len(client.payloads) == 2
    assert len(plan.actions) == 1
    assert plan.actions[0].title == "Sort scattered clothes"


def test_explicit_empty_actions_is_a_valid_zero_task_decision():
    client = ScriptedClient({"actions": []})
    plan = OpenWorldPlanner(client).propose(EVIDENCE, SceneContext())
    assert plan.actions == []
    assert len(client.payloads) == 1


def test_null_or_wrong_type_actions_fail_after_retry():
    for invalid in (None, "none", {"action_id": "a1"}):
        client = ScriptedClient({"actions": invalid}, {"actions": invalid})
        with __import__("pytest").raises(ValueError, match="must be an array"):
            OpenWorldPlanner(client).propose(EVIDENCE, SceneContext())
        assert len(client.payloads) == 2


def test_failure_logging_does_not_expose_untrusted_value_error_content(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    jobs = AutonomousJobService(sessionmaker(engine, expire_on_commit=False))
    jobs.enqueue("h", "m")
    media = SimpleNamespace(get_image=lambda *_: (SimpleNamespace(content_type="image/jpeg"), b"image"))
    private_marker = "PRIVATE_PROVIDER_RESPONSE_AND_KEY"
    records = []

    def failing_scan(**_):
        raise ValueError(private_marker)

    monkeypatch.setattr("app.services.autonomous_jobs.logger",
                        SimpleNamespace(warning=lambda message, *args: records.append(message % args)))
    assert jobs.process_one(media=media, bridge=None, build_pipeline=None, scan=failing_scan) == "retry_scheduled"
    assert records and "ValueError" in records[0]
    assert private_marker not in records[0]


def test_two_reviewers_can_identify_an_unknown_primary_room_category():
    from app.services.open_world_live import OpenWorldVision

    class CategoryReviewer:
        def ask(self, **_):
            return {"room_supported": False, "room_category": "walk-in closet",
                    "claims": [{"id": "e1", "supported": True}]}

    vision = OpenWorldVision(primary=SimpleNamespace(), independent=CategoryReviewer(),
                             additional=CategoryReviewer())
    scene = scene_with(None)
    result = vision.verify(scene, b"image", "image/jpeg")
    context, evidence = corroborate_scene(scene, result, "m1")
    assert result.category_by_reviewers
    assert context.category == "walk-in closet"
    assert len(evidence) == 1

"""Opt-in, non-persistent live open-world evaluation.

The primary model must name observable facts, not predetermined condition enums.
A separate image-aware reviewer must corroborate each visible claim; a distinct
planning step and separate image-aware action review then enforce policy checks.
No guessed effort, no extrapolation from unsupported primary claims.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError

from .open_world_planning import (ActionReview, Evidence, IndependentPlanReview,
                                  ProposedPlan, SceneContext)
from .open_world_orchestrator import plan_verified_scene


class VisualClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=5, max_length=800)


class VisualScene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    room_category: str | None = Field(default=None, max_length=120)
    claims: list[VisualClaim] = Field(max_length=20)


class ClaimVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    supported: bool


class VisualReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    room_supported: bool
    room_category: str | None = Field(default=None, max_length=120)
    category_by_reviewers: bool = False
    reviewer_votes: dict[str, dict[str, bool]] = Field(default_factory=dict)
    claims: list[ClaimVerdict]


def _category_tokens(value: str) -> set[str]:
    words = {w for w in re.sub(r"[^a-z0-9]+", " ", value.lower()).split() if w not in {"room", "space", "area", "walk", "in"}}
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}


def categories_agree(proposed: str, reviewed: str | None) -> bool:
    if reviewed is None:
        return True
    return bool(_category_tokens(proposed) & _category_tokens(reviewed))


class PreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    room_category: str | None
    corroborated_evidence: list[Evidence]
    approved_actions: list[dict]
    rejected_actions: dict[str, str]
    verification: str
    saved: bool = False
    proposed_count: int = 0
    proposal_reviews: list[dict] = Field(default_factory=list)
    model_audit: dict = Field(default_factory=dict)


class VisionModel(Protocol):
    def compare_changes(self, reference: bytes, reference_type: str, current: bytes, current_type: str) -> tuple[list[VisualClaim], dict]: ...
    def extract(self, image: bytes, media_type: str) -> VisualScene: ...
    def verify(self, scene: VisualScene, image: bytes, media_type: str) -> VisualReview: ...


def corroborate_scene(scene: VisualScene, review: VisualReview, media_id: str) -> tuple[SceneContext, list[Evidence]]:
    if len({c.id for c in scene.claims}) != len(scene.claims):
        raise ValueError("Duplicate visual claim IDs")
    if len(review.claims) != len(scene.claims) or {v.id for v in review.claims} != {c.id for c in scene.claims}:
        raise ValueError("Review did not address every visual claim")
    if len({v.id for v in review.claims}) != len(review.claims):
        raise ValueError("Duplicate reviewer claims")
    valid = {v.id for v in review.claims if v.supported}
    evidence = [Evidence(id=c.id, description=c.description, provenance="visible", source_id=media_id)
                for c in scene.claims if c.id in valid]
    if review.category_by_reviewers and review.room_category:
        category = review.room_category
    else:
        category = scene.room_category if review.room_supported and scene.room_category else None
        if category and not categories_agree(category, review.room_category):
            category = None
    return SceneContext(category=category, category_supported=bool(category)), evidence


def preview_verified_scene(*, image: bytes, media_type: str, media_id: str,
                           vision: VisionModel, planner, reviewer,
                           existing_tasks: list[dict] | None = None,
                           active_task_keys: set[str] | None = None,
                           reference_image: bytes | None = None,
                           reference_media_type: str | None = None) -> PreviewResult:
    if not image or media_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Unsupported media")
    scene = vision.extract(image, media_type)
    review = vision.verify(scene, image, media_type)
    confirmed_scene, evidence = corroborate_scene(scene, review, media_id)
    model_audit = {"primary_claims": [c.model_dump() for c in scene.claims],
                   "review_votes": review.reviewer_votes,
                   "retained_single_image_ids": [e.id for e in evidence]}
    if reference_image is not None:
        if reference_media_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Reference media type required for paired scan")
        if callable(getattr(vision, "compare_changes", None)):
            try:
                pair_claims, pair_audit = vision.compare_changes(
                    reference_image, reference_media_type, image, media_type)
            except Exception as exc:



                pair_claims, pair_audit = [], {
                    "status": "unavailable", "error_type": type(exc).__name__}
        else:
            pair_claims, pair_audit = [], {"status": "unsupported_in_current_model_mode"}
        existing_ids = {e.id for e in evidence}
        if any(c.id in existing_ids for c in pair_claims):
            raise ValueError("Paired and single-image claim IDs collided")
        evidence.extend(Evidence(id=c.id, description=c.description, provenance="visible", source_id=media_id)
                        for c in pair_claims)
        model_audit["paired_comparison"] = pair_audit
    if not evidence:
        return PreviewResult(room_category=confirmed_scene.category, corroborated_evidence=[],
                             approved_actions=[], rejected_actions={}, verification="no_corroborated_evidence", model_audit=model_audit)
    planned = plan_verified_scene(corroborated_evidence=evidence,
                                  independently_supported_scene=confirmed_scene,
                                  original_media=image, media_type=media_type,
                                  planner=planner, reviewer=reviewer,
                                  existing_tasks=existing_tasks, active_task_keys=active_task_keys)
    return PreviewResult(room_category=confirmed_scene.category, corroborated_evidence=evidence,
                         approved_actions=[a.model_dump(mode="json") for a in planned.outcome.approved],
                         rejected_actions=planned.outcome.rejected, verification="reviewed",
                         proposed_count=planned.proposed_count,
                         proposal_reviews=planned.proposal_reviews, model_audit=model_audit)


def _read_json_text(raw: str):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Missing model JSON")
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```" or lines[0].lower().strip() not in {"```json", "```"}:
            raise ValueError("Malformed JSON fence")
        text = "\n".join(lines[1:-1]).strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Model response must be object")
    return value


class OpenAIJsonClient:
    """OpenAI vision/text adapter, using the already configured review model."""
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def ask(self, *, instruction: str, payload: dict | None = None, image: bytes | None = None,
            media_type: str = "image/jpeg", max_tokens: int = 2200) -> dict:
        content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False) if payload is not None else "Analyze the image."}]
        if image is not None:
            content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{base64.b64encode(image).decode('ascii')}"}})
        response = self.client.chat.completions.create(model=self.model,
            messages=[{"role": "system", "content": instruction}, {"role": "user", "content": content}],
            max_tokens=max_tokens)
        if not response.choices or response.choices[0].finish_reason == "length":
            raise ValueError("Response truncated")
        return _read_json_text(response.choices[0].message.content)


class AnthropicJsonClient:
    """Separate independently image-aware Anthropic reviewer."""
    def __init__(self, client, model: str, key: str, strict_structure: bool = False):
        self.client, self.model, self.key = client, model, key
        self.strict_structure = strict_structure

    def ask(self, *, instruction: str, payload: dict, image: bytes, media_type: str,
            max_tokens: int = 2400, schema_kind: str | None = None) -> dict:

        if self.model.startswith("claude-opus-5-5"):
            max_tokens = max(6500, max_tokens * 3)
        request = {"model": self.model, "max_tokens": max_tokens, "system": instruction,
                   "messages": [{"role": "user", "content": [
                       {"type": "text", "text": json.dumps(payload, ensure_ascii=False)},
                       {"type": "image", "source": {"type": "base64", "media_type": media_type,
                            "data": base64.b64encode(image).decode("ascii")}}]}]}
        if self.strict_structure:
            from app.services.accuracy_models import SCHEMAS
            if schema_kind not in SCHEMAS:
                raise ValueError("Anthropic request missing structured schema")
            request["output_config"] = {"format": {
                "type": "json_schema", "schema": SCHEMAS[schema_kind]}}
        response = self.client.post("https://api.anthropic.com/v1/messages", json=request,
                                    headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        response.raise_for_status()
        data = response.json()
        if data.get("stop_reason") == "max_tokens":
            raise ValueError("Reviewer truncated")
        blocks = [p.get("text", "") for p in data.get("content", []) if p.get("type") == "text"]
        return _read_json_text("\n".join(blocks))


    def verify_pair_changes(self, reference: bytes, reference_type: str,
                            current: bytes, current_type: str, claims: list[dict]) -> dict:
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if not reference or not current or reference_type not in allowed or current_type not in allowed:
            raise ValueError("Unsupported comparison media")
        blocks = [
            {"type": "text", "text": json.dumps({"proposed_changes": claims}, ensure_ascii=False)},
            {"type": "text", "text": "REFERENCE photograph:"},
            {"type": "image", "source": {"type": "base64", "media_type": reference_type,
                                          "data": base64.b64encode(reference).decode("ascii")}},
            {"type": "text", "text": "CURRENT photograph:"},
            {"type": "image", "source": {"type": "base64", "media_type": current_type,
                                          "data": base64.b64encode(current).decode("ascii")}},
        ]
        request = {"model": self.model, "max_tokens": 6500 if self.model.startswith("claude-opus-5-5") else 2400,
                   "system": (
                       "INDEPENDENT two-image visual verification. Compare the reference to the current "
                       "physical room. Return exactly one supported:boolean for each proposed change ID. "
                       "Only confirm directly observable differences. Physical disappearance is NOT "
                       "proven when an object may be outside the frame, occluded, behind another object, "
                       "or represented on a screen or mirror. Condition changes need visible evidence. "
                       "Reject unsupported claims; do not create new changes."
                   ), "messages": [{"role": "user", "content": blocks}]}
        if self.strict_structure:
            from app.services.accuracy_models import SCHEMAS
            request["output_config"] = {"format": {"type": "json_schema", "schema": SCHEMAS["pair_review"]}}
        response = self.client.post("https://api.anthropic.com/v1/messages", json=request,
                                    headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        response.raise_for_status()
        data = response.json()
        if data.get("stop_reason") == "max_tokens":
            raise ValueError("Pair review truncated")
        return _read_json_text("\n".join(part.get("text", "") for part in data.get("content", [])
                                           if part.get("type") == "text"))


class OpenWorldVision:
    def __init__(self, primary: OpenAIJsonClient, independent: AnthropicJsonClient,
                 additional: OpenAIJsonClient | None = None):
        self.primary, self.independent, self.additional = primary, independent, additional

    def compare_changes(self, reference: bytes, reference_type: str,
                        current: bytes, current_type: str) -> tuple[list[VisualClaim], dict]:
        """Conservative paired evidence for *already verified* same-room scans.

        Production checks physical room continuity before calling this method.
        Unverified disappearances and uncertain visibility are never action evidence.
        """
        if not (callable(getattr(self.primary, "compare_changes", None))
                and callable(getattr(self.independent, "verify_pair_changes", None))
                and self.additional is not None
                and callable(getattr(self.additional, "compare_changes", None))):
            return [], {"status": "unsupported_in_current_model_mode"}
        raw = self.primary.compare_changes(reference, reference_type, current, current_type)
        proposed = raw.get("changes")
        if not isinstance(proposed, list) or len(proposed) > 12:
            raise ValueError("Invalid model-proposed pair changes")
        ids = [item.get("id") for item in proposed if isinstance(item, dict)]
        allowed = _PAIR_ACTIONABLE | {"visibility", "lighting"}
        if (len(ids) != len(proposed) or len(ids) != len(set(ids))
                or any(not isinstance(item.get("id"), str) or not item["id"].startswith("p")
                       or len(item["id"]) > 80 or item.get("change_type") not in allowed
                       or not isinstance(item.get("description"), str)
                       or not 5 <= len(item["description"]) <= 800 for item in proposed)):
            raise ValueError("Invalid pair change claim structure")
        if not proposed:
            return [], {"status": "no_visible_changes", "proposed": []}
        first = _checked_pair_votes(proposed, self.independent.verify_pair_changes(
            reference, reference_type, current, current_type, proposed))
        second = _checked_pair_votes(proposed, self.additional.compare_changes(
            reference, reference_type, current, current_type, proposed))
        accepted = [VisualClaim(id=item["id"], description=item["description"])
                    for item in proposed if item["change_type"] in _PAIR_ACTIONABLE
                    and first[item["id"]] and second[item["id"]]]
        audit = {"status": "reviewed", "proposed": [
            {"id": item["id"], "change_type": item["change_type"],
             "description": item["description"], "claude_supported": first[item["id"]],
             "terra_supported": second[item["id"]],
             "accepted_as_action_evidence": item["id"] in {c.id for c in accepted}}
            for item in proposed]}
        return accepted, audit

    def extract(self, image: bytes, media_type: str) -> VisualScene:
        result = self.primary.ask(instruction=(
            "Analyze household image. Return ONLY JSON {room_category:string|null,claims:[{id:string,description:string}]}. "
            "No fixed taxonomy: describe at most 12 directly visible actionable conditions in plain language, "
            "one concrete fact per claim. Identify likely room CATEGORY, not exact identity. "
            "Determine space category from the built-in arrangement and defining architectural fixtures, "
            "not just the loose objects present. Storage rails, built-in shelving, appliances, and plumbing "
            "are different kinds of evidence; clothes alone never prove a laundry room. "
            "If the room category is unclear, use null. "
            "Explicitly describe any visible blocked access, scattered belongings, disorganized storage, "
            "or items obstructing walkable floor areas as observations when they are apparent. "
            "Do not assume clothing is dirty, infer unseen conditions, or make recommendations. "
            "When nothing actionable is visible, use empty claims. Use unique IDs e1,e2,..."),
            image=image, media_type=media_type,
            **({"schema_kind": "scene"} if getattr(self.primary, "structured_outputs", False) else {}))
        return VisualScene.model_validate(result)

    def verify(self, scene: VisualScene, image: bytes, media_type: str) -> VisualReview:
        result = self.independent.ask(instruction=(
            "Independent image verifier. Return ONLY JSON {room_supported:boolean,room_category:string|null,claims:[{id:string,supported:boolean}]}. "
            "room_category is YOUR OWN name for this space judged from fixed fixtures; use null if unclear. "
            "Review EACH claim against ORIGINAL image. Each id exactly once. Mark unsupported if objects, condition, "
            "clean/dirty status, or quantity cannot actually be seen. room_supported only if the proposed room category "
            "is supported by visual evidence, considering fixed room layout and fixtures rather than "
            "movable objects alone. A cluttered room cannot be classified as a laundry room merely "
            "because clothes are visible. Do not create new claims."),
            payload=scene.model_dump(mode="json"), image=image, media_type=media_type,
            **({"schema_kind": "review"} if getattr(self.independent, "strict_structure", False) else {}))
        reviewed = VisualReview.model_validate(result)
        if self.additional is None:
            return reviewed
        second_result = self.additional.ask(instruction=(
            "Independently verify the proposed scene from the ORIGINAL image. "
            "Return ONLY JSON {room_supported:boolean,room_category:string|null,claims:[{id:string,supported:boolean}]}. "
            "room_category is YOUR OWN name for this space judged from fixed fixtures; use null if unclear. "
            "Check every supplied claim ID exactly once. Withhold unsupported visual assertions "
            "such as a pile of clothes proving that washing is needed."
        ), payload=scene.model_dump(mode="json"), image=image, media_type=media_type,
            **({"schema_kind": "review"} if getattr(self.additional, "structured_outputs", False) else {}))
        second = VisualReview.model_validate(second_result)
        claimed = {claim.id for claim in scene.claims}
        first_ids = [claim.id for claim in reviewed.claims]
        second_ids = [claim.id for claim in second.claims]
        if set(first_ids) != claimed or len(first_ids) != len(claimed):
            raise ValueError("First independent review did not address every claim")
        if set(second_ids) != claimed or len(second_ids) != len(claimed):
            raise ValueError("Second independent review did not address every claim")
        validated = {item.id: item.supported for item in second.claims}
        labels = [x for x in (reviewed.room_category, second.room_category) if x]
        reviewers_agree = len(labels) == 2 and categories_agree(labels[0], labels[1])
        proposal_agrees = (scene.room_category is not None
                           and all(categories_agree(scene.room_category, x) for x in labels))
        override = reviewers_agree and not proposal_agrees
        return VisualReview(
            room_supported=override or (reviewed.room_supported and second.room_supported
                                        and (reviewers_agree or not labels)),
            room_category=labels[0] if labels else None,
            category_by_reviewers=override,
            reviewer_votes={"claude": {c.id: c.supported for c in reviewed.claims},
                            "terra": {c.id: c.supported for c in second.claims}},
            claims=[ClaimVerdict(id=item.id, supported=item.supported and validated[item.id])
                    for item in reviewed.claims],
        )


_PAIR_ACTIONABLE = frozenset({"addition", "removal", "condition", "relocation"})


def _checked_pair_votes(changes: list[dict], result: dict) -> dict[str, bool]:
    """Fail closed on missing, duplicate, extraneous or non-boolean judgments."""
    decisions = result.get("changes")
    if not isinstance(decisions, list):
        raise ValueError("Pair reviewer did not return changes")
    expected = {item["id"] for item in changes}
    ids = [item.get("id") for item in decisions if isinstance(item, dict)]
    if (len(ids) != len(decisions) or len(ids) != len(set(ids)) or set(ids) != expected
            or any(type(item.get("supported")) is not bool for item in decisions)):
        raise ValueError("Pair reviewer must assess each proposed change exactly once")
    return {item["id"]: item["supported"] for item in decisions}


class OpenWorldPlanner:
    """Generate actions with a strict, bounded schema-repair attempt.

    Repair always asks the model to regenerate the complete plan. It never
    coerces a duration, changes supporting evidence, or bypasses validation.
    """

    def __init__(self, client: OpenAIJsonClient):
        self.client = client

    def propose(self, evidence: list[Evidence], scene: SceneContext,
                existing_tasks: list[dict] | None = None) -> ProposedPlan:
        payload = {
            "scene": scene.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        if existing_tasks:
            payload["existing_tasks"] = existing_tasks
        instruction = (
            "You are a general-purpose household planner. Return ONLY a JSON object with the single key "
            "actions. Scene and evidence are context and must not be returned. "
            "If existing_tasks is supplied, never propose work that an existing task already covers, "
            "even in different words. The actions value must be an array. Each action must include: action_id (string), "
            "title (string), action (string), observation_location (string or null), "
            "action_location (string or null), supporting_evidence_ids (array of existing evidence IDs), "
            "prerequisites (array of strings), assumptions (array of strings), "
            "verification_criteria (string), estimated_effort, requires_user_confirmation (boolean), "
            "hazard_or_professional_help (boolean). No additional fields. "
            "estimated_effort MUST be JSON null OR an object with exactly four keys: "
            "minimum_minutes (integer), maximum_minutes (integer), rationale (string), "
            "evidence_ids (array of existing evidence IDs). Never use strings, bare numbers, arrays, "
            "or empty objects as estimated_effort. Both minute bounds must be positive and ordered, "
            "and the explanation and evidence IDs must support the estimate; otherwise use JSON null. "
            "Do not invent minutes or evidence. No predetermined room or task taxonomy. "
            "Propose only a justified, useful, proportionate action supported by visible evidence; "
            "Evaluate whether visible obstruction, lack of accessible storage, or scattered belongings "
            "support a useful, optional, reversible action. Task proposals are suggestions a person "
            "may accept or decline, not claims that a chore is mandatory. "
            "When a person's intended use or destination for visible items is unknown, propose only "
            "intent-neutral work: for example, check whether loose items are intentionally staged "
            "and, only if the person wants the area cleared, sort them by the person's chosen "
            "destination. Do not command putting items away, washing, donating, or discarding "
            "based solely on seeing them out of storage. Set requires_user_confirmation=true "
            "if deciding what to do with belongings depends on that person's preference. "
            "Verification criteria must separate observable change from user-confirmed intent; "
            "do not claim a photo verifies what a person intended. "
            "Consider that object placement, open/closed state, or clutter might be intentional. "
            "Do not infer dirt, damage, danger, expiration, or user intent from appearance alone. "
            "Do not invent a physical room identity, create overlapping chores, or require action "
            "without sufficient evidence. Prefer minimal reversible work, and suggest no actions "
            "when none are warranted. Flag hazardous work for user confirmation."
        )
        last_error = None
        for attempt in range(2):
            prompt = instruction
            if attempt:

                summary = [
                    {"field": ".".join(map(str, error["loc"])), "type": error["type"]}
                    for error in last_error.errors(include_input=False)
                ] if isinstance(last_error, ValidationError) else [{"type": type(last_error).__name__}]
                prompt += (
                    " Your previous response failed schema validation. Generate a NEW COMPLETE "
                    "response and correct these errors: " + json.dumps(summary) +
                    ". Do not fabricate time estimates to satisfy the schema."
                )
            try:
                response = self.client.ask(instruction=prompt, payload=payload,
                    **({"schema_kind": "actions"} if getattr(self.client, "structured_outputs", False) else {}))
                if not isinstance(response, dict) or "actions" not in response:
                    raise ValueError("Planner response missing required actions field")
                if not isinstance(response["actions"], list):
                    raise ValueError("Planner actions must be an array")
                return ProposedPlan.model_validate({
                    "scene": scene.model_dump(mode="json"),
                    "evidence": [item.model_dump(mode="json") for item in evidence],
                    "actions": response["actions"],
                })
            except (ValidationError, ValueError) as exc:
                last_error = exc
        raise last_error


class NecessityReview(BaseModel):
    """Strict, independently generated action assessment, not only image verification."""
    model_config = ConfigDict(extra="forbid")
    action_id: str
    directly_supported: bool
    feasible: bool
    no_unsupported_assumptions: bool
    safety_appropriate: bool
    necessary_or_useful: bool
    proportionate: bool
    nonredundant: bool
    intent_and_state_respected: bool
    explanation: str = Field(min_length=12, max_length=500)

    @field_validator("explanation", mode="before")
    @classmethod
    def constrain_review_explanation(cls, value):


        if isinstance(value, str) and len(value) > 500:
            return value[:400].rstrip()
        return value


class StrictIndependentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviews: list[NecessityReview] = Field(max_length=20)


def gate_action_necessity(plan: ProposedPlan, result: StrictIndependentReview) -> IndependentPlanReview:
    """Fail closed: an action must be useful, justified and not presumptive.

    The downstream deterministic validator still checks evidence IDs, safety,
    missing reviews, stable keys, and duplicate active work.
    """
    expected = {action.action_id for action in plan.actions}
    ids = [review.action_id for review in result.reviews]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise ValueError("Independent necessity review must cover each action exactly once")
    return IndependentPlanReview(reviews=[ActionReview(
        action_id=review.action_id,
        failed_gates=[name for name, passed in (
            ("not_directly_supported", review.directly_supported),
            ("not_necessary", review.necessary_or_useful),
            ("not_proportionate", review.proportionate),
            ("redundant", review.nonredundant),
            ("intent_or_state_presumed", review.intent_and_state_respected),
            ("not_feasible", review.feasible),
            ("unsupported_assumptions", review.no_unsupported_assumptions),
            ("unsafe", review.safety_appropriate)) if not passed],
        directly_supported=(review.directly_supported and review.necessary_or_useful
                            and review.proportionate and review.nonredundant
                            and review.intent_and_state_respected),
        feasible=review.feasible,
        no_unsupported_assumptions=review.no_unsupported_assumptions,
        safety_appropriate=review.safety_appropriate,
        explanation=review.explanation[:400],
    ) for review in result.reviews])


class OpenWorldActionReviewer:
    def __init__(self, client: AnthropicJsonClient):
        self.client = client

    def review(self, plan: ProposedPlan, original_media: bytes, media_type: str) -> IndependentPlanReview:
        result = self.client.ask(instruction=(
            "You are an INDEPENDENT necessity-and-safety auditor for household tasks, with the ORIGINAL image. "
            "Return ONLY JSON object {reviews:[{action_id,directly_supported,feasible,no_unsupported_assumptions,"
            "safety_appropriate,necessary_or_useful,proportionate,nonredundant,intent_and_state_respected,explanation}]}. "
            "Every judgment is a JSON boolean except action_id/explanation. Exactly one review per action. "
            "Write a concise explanation of 12 to 350 characters per action. "
            "Do not confuse a visually true observation with an action that needs doing. "
            "Set necessary_or_useful=false for arbitrary chores with no credible benefit, such as closing a washer "
            "lid that could intentionally be open for ventilation or loading. "
            "Set intent_and_state_respected=false if an action presumes intent, cleanliness, ownership, "
            "machine state, a required storage destination, or another unseen condition. "
            "Distinguish a potentially useful, optional suggestion from a mandatory chore: "
            "necessary_or_useful is true if the action has credible user benefit even when not necessary. "
            "An intent-neutral check or conditional sorting suggestion may be useful when loose "
            "belongings or an obstruction are actually visible, provided it asks the user before "
            "choosing the items' destination and changes nothing until the user agrees. "
            "Do not reject such an action ONLY because the objects might be intentionally staged; "
            "reject commands that presume the objects must be stored, laundered, donated or discarded. "
            "Do not assume dirtiness from clothes being on the floor. "
            "Set proportionate=false when the action is unnecessarily invasive, costly, or disruptive; "
            "nonredundant=false when another proposal covers the same work. "
            "Judge EACH action independently against corroborated evidence and the original image; "
            "explain failed gates specifically, citing the action's unsupported step rather than "
            "a hypothetical not asserted by the action. Do not assume all visible objects require interaction. "
            "Never accept dangerous actions without appropriate confirmation. "
            "When the proposed action itself is unsupported or safety is uncertain, reject."
        ), payload=plan.model_dump(mode="json"), image=original_media, media_type=media_type,
            **({"schema_kind": "necessity"} if getattr(self.client, "strict_structure", False) else {}))
        return gate_action_necessity(plan, StrictIndependentReview.model_validate(result))

"""Opt-in, non-persistent live open-world evaluation.

The primary model must name observable facts, not predetermined condition enums.
A separate image-aware reviewer must corroborate each visible claim; a distinct
planning step and separate image-aware action review then enforce policy checks.
No guessed effort, no extrapolation from unsupported primary claims.
"""
from __future__ import annotations

import base64
import json
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
    claims: list[ClaimVerdict]


class PreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    room_category: str | None
    corroborated_evidence: list[Evidence]
    approved_actions: list[dict]
    rejected_actions: dict[str, str]
    verification: str
    saved: bool = False


class VisionModel(Protocol):
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
    category = scene.room_category if review.room_supported and scene.room_category else None
    return SceneContext(category=category, category_supported=bool(category)), evidence


def preview_verified_scene(*, image: bytes, media_type: str, media_id: str,
                           vision: VisionModel, planner, reviewer) -> PreviewResult:
    if not image or media_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Unsupported media")
    scene = vision.extract(image, media_type)
    review = vision.verify(scene, image, media_type)
    confirmed_scene, evidence = corroborate_scene(scene, review, media_id)
    if not evidence:
        return PreviewResult(room_category=confirmed_scene.category, corroborated_evidence=[],
                             approved_actions=[], rejected_actions={}, verification="no_corroborated_evidence")
    planned = plan_verified_scene(corroborated_evidence=evidence,
                                  independently_supported_scene=confirmed_scene,
                                  original_media=image, media_type=media_type,
                                  planner=planner, reviewer=reviewer)
    return PreviewResult(room_category=confirmed_scene.category, corroborated_evidence=evidence,
                         approved_actions=[a.model_dump(mode="json") for a in planned.outcome.approved],
                         rejected_actions=planned.outcome.rejected, verification="reviewed")


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
    def __init__(self, client, model: str, key: str):
        self.client, self.model, self.key = client, model, key

    def ask(self, *, instruction: str, payload: dict, image: bytes, media_type: str,
            max_tokens: int = 2400) -> dict:
        request = {"model": self.model, "max_tokens": max_tokens, "system": instruction,
                   "messages": [{"role": "user", "content": [
                       {"type": "text", "text": json.dumps(payload, ensure_ascii=False)},
                       {"type": "image", "source": {"type": "base64", "media_type": media_type,
                            "data": base64.b64encode(image).decode("ascii")}}]}]}
        response = self.client.post("https://api.anthropic.com/v1/messages", json=request,
                                    headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"})
        response.raise_for_status()
        data = response.json()
        if data.get("stop_reason") == "max_tokens":
            raise ValueError("Reviewer truncated")
        blocks = [p.get("text", "") for p in data.get("content", []) if p.get("type") == "text"]
        return _read_json_text("\n".join(blocks))


class OpenWorldVision:
    def __init__(self, primary: OpenAIJsonClient, independent: AnthropicJsonClient):
        self.primary, self.independent = primary, independent

    def extract(self, image: bytes, media_type: str) -> VisualScene:
        result = self.primary.ask(instruction=(
            "Analyze household image. Return ONLY JSON {room_category:string|null,claims:[{id:string,description:string}]}. "
            "No fixed taxonomy: describe at most 12 directly visible actionable conditions in plain language, "
            "one concrete fact per claim. Identify likely room CATEGORY, not exact identity. "
            "Do not assume clothing is dirty, infer unseen conditions, or make recommendations. "
            "When nothing actionable is visible, use empty claims. Use unique IDs e1,e2,..."),
            image=image, media_type=media_type)
        return VisualScene.model_validate(result)

    def verify(self, scene: VisualScene, image: bytes, media_type: str) -> VisualReview:
        result = self.independent.ask(instruction=(
            "Independent image verifier. Return ONLY JSON {room_supported:boolean,claims:[{id:string,supported:boolean}]}. "
            "Review EACH claim against ORIGINAL image. Each id exactly once. Mark unsupported if objects, condition, "
            "clean/dirty status, or quantity cannot actually be seen. room_supported only if the proposed room category "
            "is supported by visual evidence. Do not create new claims."),
            payload=scene.model_dump(mode="json"), image=image, media_type=media_type)
        return VisualReview.model_validate(result)


class OpenWorldPlanner:
    """Generate actions with a strict, bounded schema-repair attempt.

    Repair always asks the model to regenerate the complete plan. It never
    coerces a duration, changes supporting evidence, or bypasses validation.
    """

    def __init__(self, client: OpenAIJsonClient):
        self.client = client

    def propose(self, evidence: list[Evidence], scene: SceneContext) -> ProposedPlan:
        payload = {
            "scene": scene.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        instruction = (
            "You are a general-purpose household planner. Return ONLY a JSON object with keys "
            "scene, evidence, actions. Copy scene and evidence EXACTLY from the supplied input. "
            "The actions value must be an array. Each action must include: action_id (string), "
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
            "consider that object placement, open/closed state or clutter might be intentional. "
            "Do not infer dirt, damage, danger, expiration, or user intent from appearance alone. "
            "Do not invent a physical room identity, create overlapping chores, or require action "
            "without sufficient evidence. Prefer minimal reversible work, and suggest no actions "
            "when none are warranted. Flag hazardous work for user confirmation."
        )
        last_error = None
        for attempt in range(2):
            prompt = instruction
            if attempt:
                # Send error locations/types only, not raw invalid response or private media.
                summary = [
                    {"field": ".".join(map(str, error["loc"])), "type": error["type"]}
                    for error in last_error.errors(include_input=False)
                ] if isinstance(last_error, ValidationError) else [{"type": type(last_error).__name__}]
                prompt += (
                    " Your previous response failed schema validation. Generate a NEW COMPLETE "
                    "response and correct these errors: " + json.dumps(summary) +
                    ". Copy the original scene and evidence unchanged. Do not fabricate time "
                    "estimates to satisfy the schema."
                )
            try:
                response = self.client.ask(instruction=prompt, payload=payload)
                return ProposedPlan.model_validate(response)
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
        # Only shorten excess narrative. Never change the review decisions.
        # The downstream ActionReview already retains at most 400 characters.
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
            "Set intent_and_state_respected=false if the action presumes intent, cleanliness, ownership, "
            "machine state or an unseen condition. Recommend conditional sorting instead of washing "
            "unless dirtiness is established. Set proportionate=false when the action is unnecessarily "
            "invasive, costly, or disruptive; nonredundant=false when another proposal covers the same work. "
            "Judge EACH action independently against corroborated evidence and the original image; "
            "explain failed gates specifically. Do not assume all visible objects require interaction. "
            "Never accept dangerous actions without appropriate confirmation. When uncertain, reject."
        ), payload=plan.model_dump(mode="json"), image=original_media, media_type=media_type)
        return gate_action_necessity(plan, StrictIndependentReview.model_validate(result))

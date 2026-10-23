"""Independent image-aware review of household vision observations.

The second model sees the image. Its agreement is corroboration, not ground truth.
"""
import base64
import json
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .provider import VisionExtraction, SpaceCategory


class VerifiedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    visible: bool
    evidence_supported: bool
    workload_supported: bool


class IndependentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    space_category: SpaceCategory
    room_supported: bool
    claims: list[VerifiedClaim] = Field(max_length=4)


class ImageVerifier(Protocol):
    def review(self, image: bytes, content_type: str, proposed: VisionExtraction) -> IndependentReview: ...


def corroborate(proposed: VisionExtraction, review: IndependentReview) -> bool:
    """Conservative agreement. Never convert agreement into human confirmation."""
    proposed_room = proposed.space_category or SpaceCategory.UNKNOWN
    if proposed_room != SpaceCategory.UNKNOWN and (not review.room_supported or review.space_category != proposed_room):
        return False
    if len(review.claims) != len(proposed.candidates):
        return False
    claims = {claim.category: claim for claim in review.claims}
    if len(claims) != len(review.claims):
        return False
    for candidate in proposed.candidates:
        claim = claims.get(candidate.category.value)
        if not claim or not (claim.visible and claim.evidence_supported and claim.workload_supported):
            return False
    return True


class OpenAIImageVerifier:
    """Independent vision-review model; OpenAI SDK client injectable for tests."""
    def __init__(self, *, model: str, client=None):
        if not model.strip():
            raise ValueError("Independent verifier model is required")
        if client is None:
            from openai import OpenAI
            client = OpenAI(timeout=30, max_retries=1)
        self._client = client
        self._model = model

    def review(self, image: bytes, content_type: str, proposed: VisionExtraction) -> IndependentReview:
        if content_type not in {"image/png", "image/jpeg", "image/webp"} or not image:
            raise ValueError("Unsupported independent review image")
        data = base64.b64encode(image).decode("ascii")
        summary = {
            "space_category": proposed.space_category.value if proposed.space_category else "unknown",
            "claims": [{"category": c.category.value, "workload": c.value,
                        "visible_evidence": c.visible_evidence} for c in proposed.candidates],
        }
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": (
                    "You are an INDEPENDENT household image reviewer. Inspect the attached IMAGE; "
                    "do not accept another model's assertions without visual support. "
                    "Reply ONLY with JSON having space_category, room_supported, claims. "
                    "space_category must be one of kitchen, bathroom, bedroom, living_room, "
                    "laundry_room, outdoor, garage, unknown. room_supported is true only "
                    "when visual features justify the proposed category. "
                    "Each claims entry has exactly category, visible, evidence_supported, workload_supported. "
                    "Repeat a claim category only when you independently assess it; false means "
                    "unsupported. workload_supported is false if the numerical workload lacks "
                    "reasonable visual support. For occluded/out-of-frame targets use false. "
                    "Do not equate image similarity with exact physical-room identity."
                )},
                {"role": "user", "content": [
                    {"type": "text", "text": json.dumps(summary, separators=(",", ":"))},
                    {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{data}"}},
                ]},
            ],
        )
        raw = response.choices[0].message.content
        if not isinstance(raw, str):
            raise ValueError("Independent reviewer returned no text")
        raw = raw.strip()
        if raw.startswith("```") and raw.endswith("```"):
            parts = raw.splitlines()
            if len(parts) >= 3 and parts[0].lower() in ("```", "```json") and parts[-1] == "```":
                raw = "\n".join(parts[1:-1]).strip()
        return IndependentReview.model_validate(json.loads(raw))

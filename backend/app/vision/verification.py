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


def parse_review_json(raw: str) -> IndependentReview:
    """Parse a reviewer JSON object without relaxing evidence requirements."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Empty independent review")
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[0].strip().lower() in {"```", "```json"} and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()
    # No scanning arbitrary prose for braces: keep invalid model responses invalid.
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Independent reviewer did not return a JSON object")
    return IndependentReview.model_validate(value)


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
        import logging
        from pydantic import ValidationError
        log = logging.getLogger(__name__)
        messages = [
            {"role": "system", "content": (
                "You independently verify household claims against the supplied image. "
                "Return ONLY one valid JSON object, no markdown or explanations. "
                "Required top-level keys: space_category, room_supported, claims. "
                "space_category must be kitchen, bathroom, bedroom, living_room, "
                "laundry_room, outdoor, garage, or unknown. room_supported is a boolean. "
                "claims is an array with exactly one entry for each proposed category, "
                "in its original order. Every claim entry must contain exactly "
                "category (same string as proposal), visible (boolean), "
                "evidence_supported (boolean), workload_supported (boolean). "
                "Mark false when visual evidence is unclear, missing or occluded, "
                "or the workload estimate is not visually grounded. "
                "Do not infer exact physical room identity from a category."
            )},
            {"role": "user", "content": [
                {"type": "text", "text": json.dumps(summary, separators=(",", ":"))},
                {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{data}"}},
            ]},
        ]
        last_error = None
        for attempt in range(2):
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=1400 if attempt == 0 else 2400,
            )
            choices = getattr(response, "choices", ())
            choice = choices[0] if choices else None
            raw = getattr(getattr(choice, "message", None), "content", None)
            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason not in (None, "stop", "length"):
                raise ValueError("OpenAI reviewer did not finish with a usable response")
            try:
                if not isinstance(raw, str):
                    raise ValueError("OpenAI reviewer returned no text")
                review = parse_review_json(raw)
                # Truncated responses cannot be trusted even if a JSON fragment parsed.
                if finish_reason == "length":
                    raise ValueError("OpenAI reviewer response was truncated")
                return review
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                if isinstance(exc, ValidationError):
                    paths = [".".join(map(str, e.get("loc", ()))) for e in exc.errors(include_url=False, include_input=False)]
                    kinds = [e.get("type", "unknown") for e in exc.errors(include_url=False, include_input=False)]
                    log.warning("OpenAI reviewer invalid output: category=schema_validation count=%d fields=%s types=%s finish_reason=%s attempt=%d",
                                len(paths), paths[:8], kinds[:8], finish_reason, attempt + 1)
                elif isinstance(exc, json.JSONDecodeError):
                    log.warning("OpenAI reviewer invalid output: category=json_decode position=%d length=%d finish_reason=%s attempt=%d",
                                exc.pos, len(raw) if isinstance(raw, str) else 0, finish_reason, attempt + 1)
                else:
                    log.warning("OpenAI reviewer invalid output: category=missing_or_truncated finish_reason=%s attempt=%d",
                                finish_reason, attempt + 1)
        raise last_error

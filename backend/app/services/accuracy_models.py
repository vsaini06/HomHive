"""Accuracy-first OpenAI Responses adapter for autonomous household scans.

Use only when the accuracy-first setting is enabled. JSON schema describes the
existing HomHive contracts; policy validation remains in the application.
"""
from __future__ import annotations

import base64
import json


def _obj(fields: dict) -> dict:
    return {"type": "object", "properties": fields, "required": list(fields),
            "additionalProperties": False}


def _array(item: dict) -> dict:
    return {"type": "array", "items": item}


STR = {"type": "string"}
BOOL = {"type": "boolean"}
INT = {"type": "integer"}
NULL_STR = {"type": ["string", "null"]}

SCHEMAS = {
    "scene": _obj({
        "room_category": NULL_STR,
        "claims": _array(_obj({"id": STR, "description": STR})),
    }),
    "review": _obj({
        "room_supported": BOOL,
        "room_category": NULL_STR,
        "claims": _array(_obj({"id": STR, "supported": BOOL})),
    }),
    "pair_changes": _obj({
        "changes": _array(_obj({
            "id": STR,
            "change_type": {"type": "string", "enum": ["addition", "removal", "condition", "relocation", "visibility", "lighting"]},
            "description": STR,
        })),
    }),
    "pair_review": _obj({
        "changes": _array(_obj({"id": STR, "supported": BOOL})),
    }),
    "room_pair": _obj({
        "same_physical_room": BOOL,
        "explanation": STR,
    }),
    "necessity": _obj({
        "reviews": _array(_obj({
            "action_id": STR,
            "directly_supported": BOOL,
            "feasible": BOOL,
            "no_unsupported_assumptions": BOOL,
            "safety_appropriate": BOOL,
            "necessary_or_useful": BOOL,
            "proportionate": BOOL,
            "nonredundant": BOOL,
            "intent_and_state_respected": BOOL,
            "explanation": STR,
        })),
    }),
    "completion": _obj({
        "verdict": {"type": "string", "enum": ["completed", "still_needed", "partially_completed", "inconclusive"]},
        "criterion_verified": BOOL,
        "claim_ids": _array(STR),
        "explanation": STR,
        "progress_percent": {"type": ["integer", "null"]},
        "next_step": NULL_STR,
    }),
    "actions": _obj({
        "actions": _array(_obj({
            "action_id": STR,
            "title": STR,
            "action": STR,
            "observation_location": NULL_STR,
            "action_location": NULL_STR,
            "supporting_evidence_ids": _array(STR),
            "prerequisites": _array(STR),
            "assumptions": _array(STR),
            "verification_criteria": STR,
            "estimated_effort": {"anyOf": [
                {"type": "null"},
                _obj({
                    "minimum_minutes": INT,
                    "maximum_minutes": INT,
                    "rationale": STR,
                    "evidence_ids": _array(STR),
                }),
            ]},
            "requires_user_confirmation": BOOL,
            "hazard_or_professional_help": BOOL,
        })),
    }),
}


class AccuracyOpenAIJsonClient:
    """Adapter honoring the existing .ask() contract with strict Responses JSON."""
    structured_outputs = True

    def __init__(self, client, model: str, *, effort: str = "high"):
        self.client = client
        self.model = model
        self.effort = effort

    def _generate(self, *, schema_kind: str, instruction: str, content: list,
                  max_tokens: int) -> dict:
        if schema_kind not in SCHEMAS:
            raise ValueError("Unsupported structured response kind")
        response = self.client.responses.create(
            model=self.model,
            instructions=instruction + " Return JSON matching the supplied schema.",
            input=[{"role": "user", "content": content}],
            text={"format": {"type": "json_schema", "name": "homhive_" + schema_kind,
                             "strict": True, "schema": SCHEMAS[schema_kind]}},
            reasoning={"effort": self.effort},
            max_output_tokens=max(12000, max_tokens * 4),
            store=False,
        )
        if getattr(response, "status", None) != "completed":
            raise ValueError("Accuracy model response incomplete")
        raw = getattr(response, "output_text", None)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Accuracy model returned no structured output")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Accuracy model returned non-object")
        return result

    def ask(self, *, instruction: str, payload: dict | None = None,
            image: bytes | None = None, media_type: str = "image/jpeg",
            max_tokens: int = 2200, schema_kind: str) -> dict:
        content = [{"type": "input_text", "text": json.dumps(payload, ensure_ascii=False)
                    if payload is not None else "Inspect the household image."}]
        if image is not None:
            if media_type not in {"image/jpeg", "image/png", "image/webp"}:
                raise ValueError("Unsupported image type")
            content.append({"type": "input_image", "image_url":
                            f"data:{media_type};base64,{base64.b64encode(image).decode('ascii')}",
                            "detail": "high"})
        return self._generate(schema_kind=schema_kind, instruction=instruction,
                              content=content, max_tokens=max_tokens)

    def compare_rooms(self, first: bytes, first_type: str,
                      second: bytes, second_type: str) -> dict:
        if not first or not second or first_type not in {"image/jpeg", "image/png", "image/webp"} or second_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Unsupported room comparison media")
        return self._generate(
            schema_kind="room_pair", max_tokens=1200,
            instruction=(
                "Compare two household photographs in order. Do they show the SAME PHYSICAL ROOM? "
                "A shared room type, matching furniture, or similar clutter is insufficient. "
                "Compare fixed geometry, architectural fixtures, countertops, windows, doors, and "
                "persistent landmarks. Lighting, viewpoint, cropping, or moved items may differ. "
                "If the physical match cannot be supported, answer false."
            ),
            content=[
                {"type": "input_text", "text": "Reference room, followed by new photograph."},
                {"type": "input_image", "image_url": f"data:{first_type};base64,{base64.b64encode(first).decode('ascii')}", "detail": "high"},
                {"type": "input_image", "image_url": f"data:{second_type};base64,{base64.b64encode(second).decode('ascii')}", "detail": "high"},
            ],
        )


    def compare_changes(self, reference: bytes, reference_type: str,
                        current: bytes, current_type: str, claims: list[dict] | None = None) -> dict:
        """Compare *both* full images, never treat a crop or occlusion as a removal.

        With claims=None the model proposes differences. With claims supplied it
        independently verifies only those proposed differences.
        """
        allowed = {"image/jpeg", "image/png", "image/webp"}
        if not reference or not current or reference_type not in allowed or current_type not in allowed:
            raise ValueError("Unsupported pair comparison media")
        reviewing = claims is not None
        instruction = (
            "You are independently verifying proposed changes between two photographs of the "
            "SAME PHYSICAL HOUSEHOLD ROOM. Compare the first reference and second current image. "
            "For EACH proposed change ID output whether the images truly support it. A crop, "
            "obstruction, viewpoint difference, reflection or screen depiction must never count "
            "as physical object removal or addition. Reject unsupported or ambiguous differences. "
            "Return an entry for every claim ID exactly once."
            if reviewing else
            "Compare TWO photographs of the same physical household room, first reference then "
            "current. Identify up to 12 independently observable PHYSICAL changes, with unique "
            "IDs p1,p2,... . Distinguish object addition, physical removal, changed condition, "
            "relocation, visibility/crop/occlusion, and lighting changes. Describe which objects "
            "changed and HOW. Distinguish a missing item from one merely cropped, hidden, or "
            "obscured; if removal is uncertain, classify as visibility, not removal. "
            "Distinguish TV/photo/reflection depictions from a physical person. "
            "Do not invent changes or tasks; return an empty array if none are supported."
        )
        content = [{"type": "input_text", "text": (
            json.dumps({"proposed_changes": claims}, ensure_ascii=False)
            if reviewing else "Reference image first, current image second.")},
            {"type": "input_image", "image_url": f"data:{reference_type};base64,{base64.b64encode(reference).decode('ascii')}", "detail": "high"},
            {"type": "input_image", "image_url": f"data:{current_type};base64,{base64.b64encode(current).decode('ascii')}", "detail": "high"}]
        return self._generate(schema_kind="pair_review" if reviewing else "pair_changes",
                              instruction=instruction, content=content, max_tokens=2200)

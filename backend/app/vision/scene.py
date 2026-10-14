import base64
import json
import os
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.config import load_local_environment
from app.media.service import MAX_IMAGE_BYTES, detected_image_type


Condition = Literal[
    "not_assessed",
    "unknown",
    "visibly_clean",
    "visibly_dirty",
    "visibly_damaged",
    "visibly_stressed",
]

ASSESSMENTS = {
    "visibly_clean",
    "visibly_dirty",
    "visibly_damaged",
    "visibly_stressed",
}


class SceneEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    evidence: str = Field(min_length=1, max_length=300)
    area: str = Field(min_length=1, max_length=100)
    condition: Condition
    condition_evidence: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def check_evidence(self):
        if not self.label.strip() or not self.area.strip() or not self.evidence.strip():
            raise ValueError("Scene entity requires visible evidence")

        if self.condition in ("not_assessed", "unknown"):
            if self.condition_evidence is not None:
                raise ValueError("Unknown entity condition cannot claim evidence")
        elif not self.condition_evidence or not self.condition_evidence.strip():
            raise ValueError("Assessed condition requires explicit visible evidence")

        return self


class RejectedAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_index: int = Field(ge=0)
    label: str
    claimed_condition: str
    reason: Literal["missing_condition_evidence"]


class SceneInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=1, max_length=255)
    entities: list[SceneEntity] = Field(max_length=100)
    needs_review: bool
    rejected_assessments: list[RejectedAssessment] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_scene(self):
        if not self.location.strip():
            raise ValueError("Scene location is required")

        if not self.entities and not self.needs_review:
            raise ValueError("Empty scene requires review")

        if self.rejected_assessments and not self.needs_review:
            raise ValueError("Rejected assessments require review")

        return self


class DetectedSceneEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    evidence: str = Field(min_length=1, max_length=300)
    area: str = Field(min_length=1, max_length=100)


class DetectedScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: list[DetectedSceneEntity] = Field(max_length=100)
    needs_review: bool


SCENE_PROMPT = (
    "Inventory distinct visible household objects and areas, not just objects with problems. "
    "Return a single JSON object with keys entities and needs_review. "
    "Do not include location: the application supplies it. "
    "For each entity include exactly label, area, evidence, condition, condition_evidence. "
    "Provide a short common label and evidence describing the visible object; area describes visible placement. "
    "Condition must be one of not_assessed, unknown, visibly_clean, visibly_dirty, visibly_damaged, visibly_stressed. "
    "Use not_assessed for objects with no meaningful assessment, and unknown if the condition cannot be judged. "
    "For visibly_* conditions, condition_evidence must describe the direct visual indication. "
    "For not_assessed and unknown, condition_evidence must be JSON null, not the string \"null\". "
    "A plant being present does not mean it is stressed; a sponge does not imply dirty dishes. "
    "Do not estimate household workload, confidence, tasks, or identity across photos. "
    "Do not invent hidden objects. Include up to 100 directly visible entities. "
    "If important objects are obscured or ambiguity remains, set needs_review true. "
    "If no objects are identifiable, return entities [] and needs_review true. "
    "Return valid JSON only, without Markdown fences or commentary."
)

DETECTION_PROMPT = (
    "Inventory distinct physical household objects and fixtures that are directly visible in the image. "
    "Focus only on object discovery and visible evidence. Do not assess cleanliness, damage, health, urgency, workload, or tasks. "
    "Return one JSON object with exactly entities and needs_review. "
    "Each entity must contain exactly label, area, evidence. "
    "Use short common labels, describe where the object appears, and give concrete visible evidence that supports the detection. "
    "Count fixed fixtures such as sinks and faucets as entities when they are visibly distinct. "
    "Do not list abstract regions, shadows, reflections, textures, or the same physical object twice. "
    "Do not guess hidden or off-frame objects. Do not use confidence scores. "
    "Include all clearly visible household entities up to 100 items. "
    "Set needs_review true when important portions of the scene are obscured or object identity is materially ambiguous. "
    "If no object is identifiable, return entities [] and needs_review true. "
    "Return valid JSON only, without Markdown fences or commentary."
)


def parse_scene_response(content: str) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Invalid scene provider response: empty text")

    raw = content.strip()
    fenced = re.fullmatch(
        r"```(?:json)?[ \t]*\n(.*?)\n```",
        raw,
        re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        raw = fenced.group(1).strip()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid scene provider response: malformed JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid scene provider response: expected object")

    return payload


def validate_scene_payload(payload: dict, location: str) -> SceneInventory:
    if set(payload) - {"location", "entities", "needs_review"}:
        raise ValueError("Invalid scene provider response: unexpected scene fields")

    if "location" in payload and payload["location"] != location:
        raise ValueError("Scene location mismatch")

    items = payload.get("entities")
    if (
        not isinstance(items, list)
        or len(items) > 100
        or not isinstance(payload.get("needs_review"), bool)
    ):
        raise ValueError("Invalid scene provider response: invalid scene structure")

    validated = []
    rejected = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError("Invalid scene provider response: invalid entity structure")

        condition = item.get("condition")
        evidence = item.get("condition_evidence")

        if condition in ("unknown", "not_assessed") and evidence == "null":
            item = {**item, "condition_evidence": None}
            evidence = None

        if condition in ASSESSMENTS and (
            evidence is None or (isinstance(evidence, str) and not evidence.strip())
        ):
            amended = dict(item)
            amended["condition"] = "unknown"
            amended["condition_evidence"] = None

            try:
                entity = SceneEntity.model_validate(amended)
            except ValidationError as exc:
                raise ValueError("Invalid scene provider response: invalid entity structure") from exc

            rejected.append(
                RejectedAssessment(
                    entity_index=index,
                    label=entity.label,
                    claimed_condition=condition,
                    reason="missing_condition_evidence",
                )
            )
        else:
            try:
                entity = SceneEntity.model_validate(item)
            except ValidationError as exc:
                raise ValueError("Invalid scene provider response: invalid entity structure") from exc

        validated.append(entity)

    try:
        return SceneInventory(
            location=location,
            entities=validated,
            needs_review=payload["needs_review"] or bool(rejected),
            rejected_assessments=rejected,
        )
    except ValidationError as exc:
        raise ValueError("Invalid scene provider response: invalid scene structure") from exc


def validate_detection_payload(payload: dict, location: str) -> SceneInventory:
    if set(payload) - {"entities", "needs_review"}:
        raise ValueError("Invalid scene provider response: unexpected detection fields")

    try:
        detected = DetectedScene.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Invalid scene provider response: invalid detection structure") from exc

    entities = [
        SceneEntity(
            label=item.label,
            area=item.area,
            evidence=item.evidence,
            condition="not_assessed",
            condition_evidence=None,
        )
        for item in detected.entities
    ]

    try:
        return SceneInventory(
            location=location,
            entities=entities,
            needs_review=detected.needs_review,
        )
    except ValidationError as exc:
        raise ValueError("Invalid scene provider response: invalid detection structure") from exc


class NebiusSceneProvider:
    def __init__(self, client=None, model: str = "openbmb/MiniCPM-V-4_5"):
        if client is None:
            load_local_environment()
            from openai import OpenAI

            key = os.environ.get("NEBIUS_API_KEY")
            if not key:
                raise ValueError("NEBIUS_API_KEY is required")

            client = OpenAI(
                base_url="https://api.tokenfactory.nebius.com/v1/",
                api_key=key,
                timeout=30.0,
                max_retries=1,
            )

        self._client = client
        self._model = model

    def _request(self, image: bytes, content_type: str, location: str, prompt: str) -> dict:
        if not image or len(image) > MAX_IMAGE_BYTES or detected_image_type(image) != content_type:
            raise ValueError("Unsupported image content")

        if not location or not location.strip() or len(location) > 255:
            raise ValueError("Invalid scene location")

        encoded = base64.b64encode(image).decode("ascii")
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Location: {location}"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
        )

        if not response.choices or not isinstance(response.choices[0].message.content, str):
            raise ValueError("Invalid scene provider response: no text")

        return parse_scene_response(response.choices[0].message.content)

    def inventory(self, image: bytes, content_type: str, location: str) -> SceneInventory:
        payload = self._request(image, content_type, location, SCENE_PROMPT)
        return validate_scene_payload(payload, location)

    def detect(self, image: bytes, content_type: str, location: str) -> SceneInventory:
        payload = self._request(image, content_type, location, DETECTION_PROMPT)
        return validate_detection_payload(payload, location)

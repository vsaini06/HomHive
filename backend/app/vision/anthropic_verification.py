
"""Independent Anthropic image verification for household observations.

The original image is supplied to the reviewer. Model agreement is
corroboration, not proof or human confirmation.

Diagnostics report only failure categories, never credentials, images,
raw provider responses, or household-specific content.
"""

import base64
import json
import logging
import os

import httpx
from pydantic import ValidationError

from .provider import VisionExtraction
from .verification import IndependentReview, parse_review_json


logger = logging.getLogger(__name__)


def _classify_failure(exc: Exception) -> str:
    """Return a safe diagnostic category without exposing exception details."""

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code

        if status in (401, 403):
            return "authentication_or_permission"

        if status == 402:
            return "billing_or_credits"

        if status == 429:
            return "rate_limit"

        if status == 400:
            return "invalid_request"

        if status == 404:
            return "model_or_endpoint_unavailable"

        if status >= 500:
            return "provider_server_error"

        return f"http_{status}"

    if isinstance(exc, httpx.TimeoutException):
        return "timeout"

    if isinstance(exc, httpx.RequestError):
        return "network_error"

    if isinstance(exc, (json.JSONDecodeError, ValidationError)):
        return "invalid_review_response"

    if isinstance(exc, ValueError):
        return "invalid_or_incomplete_response"

    return "unexpected_review_error"


class AnthropicImageVerifier:
    """Additional independent multimodal reviewer using Anthropic Messages."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        client=None,
    ):
        if not model.strip():
            raise ValueError("Anthropic model is required")

        self._model = model
        self._key = api_key or os.getenv("ANTHROPIC_API_KEY")

        if not self._key:
            raise ValueError("ANTHROPIC_API_KEY required")

        self._client = client or httpx.Client(timeout=30)
        self._owns_client = client is None

    def close(self):
        if self._owns_client:
            self._client.close()

    def review(
        self,
        image: bytes,
        content_type: str,
        proposed: VisionExtraction,
    ) -> IndependentReview:

        if content_type not in {
            "image/png",
            "image/jpeg",
            "image/webp",
        } or not image:
            raise ValueError("Unsupported Anthropic review image")

        proposed_claims = {
            "space_category": (
                proposed.space_category.value
                if proposed.space_category
                else "unknown"
            ),
            "claims": [
                {
                    "category": candidate.category.value,
                    "workload": candidate.value,
                    "visible_evidence": candidate.visible_evidence,
                }
                for candidate in proposed.candidates
            ],
        }

        for attempt in range(2):
            try:
                return self._review_once(image, content_type, proposed_claims, attempt)
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(
                    "Anthropic reviewer invalid output: attempt=%d/2 error=%s%s",
                    attempt + 1,
                    type(exc).__name__,
                    (
                        " line=%d col=%d pos=%d" % (exc.lineno, exc.colno, exc.pos)
                        if isinstance(exc, json.JSONDecodeError) else
                        " schema_error_count=%d" % len(exc.errors())
                    ),
                )
                if attempt == 1:
                    raise
            except ValueError as exc:


                if str(exc) != "Anthropic review output truncated" or attempt == 1:
                    raise
                logger.warning("Anthropic reviewer truncated output: retrying once")
        raise RuntimeError("Unexpected verifier retry state")

    def _review_once(self, image, content_type, proposed_claims, attempt):
        try:
            response = self._client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 1600 if attempt == 0 else 2400,
                    "system": (
                        "Independently inspect the supplied IMAGE. "
                        "Do not assume that proposed claims are correct. "
                        "Return JSON ONLY with exactly these fields: "
                        "space_category, room_supported, claims. "
                        "Allowed room categories: kitchen, bathroom, "
                        "bedroom, living_room, laundry_room, outdoor, "
                        "garage, unknown. "
                        "room_supported must be a boolean. "
                        "Each claim must include category, visible, "
                        "evidence_supported, and workload_supported. "
                        "All three assessment fields must be booleans. "
                        "Only support objects and conditions clearly "
                        "visible in the original image. "
                        "Do not invent exact room identity. "
                        "If a condition or numerical workload is "
                        "ambiguous, mark it unsupported. "
                        "Return one complete, syntactically valid JSON object, "
                        "without Markdown, explanations, or preamble."
                    ),
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(
                                        proposed_claims,
                                        separators=(",", ":"),
                                    ),
                                },
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": content_type,
                                        "data": base64.b64encode(
                                            image
                                        ).decode("ascii"),
                                    },
                                },
                            ],
                        }
                    ],
                },
            )

            response.raise_for_status()

            payload = response.json()

            if not isinstance(payload, dict):
                raise ValueError("Unexpected Anthropic response structure")

            stop_reason = payload.get("stop_reason")

            if stop_reason == "max_tokens":
                logger.warning(
                    "Anthropic vision verification failed: "
                    "category=incomplete_response"
                )
                raise ValueError("Anthropic review output truncated")

            blocks = payload.get("content", [])

            if not isinstance(blocks, list):
                raise ValueError("Unexpected Anthropic content structure")

            texts = [
                block["text"]
                for block in blocks
                if isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            ]

            if not texts:
                raise ValueError("Anthropic reviewer returned no text")


            raw = "".join(texts)
            logger.info(
                "Anthropic reviewer response metadata: attempt=%d "
                "stop_reason=%s block_count=%d text_length=%d",
                attempt + 1, str(stop_reason)[:32], len(texts), len(raw),
            )

            result = parse_review_json(raw)

            logger.info(
                "Anthropic vision verification completed: "
                "claim_count=%d",
                len(result.claims),
            )

            return result

        except Exception as exc:
            logger.warning(
                "Anthropic vision verification failed: category=%s",
                _classify_failure(exc),
            )
            raise

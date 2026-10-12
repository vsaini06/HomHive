
import base64
import json
import os
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import load_local_environment
from app.media.service import MAX_IMAGE_BYTES, MediaService, detected_image_type
from app.models import ConditionType


class VisionCandidate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    category: ConditionType
    value: float = Field(ge=0.0, le=1.0)
    location: str = Field(min_length=1, max_length=255)
    visible_evidence: str = Field(min_length=1, max_length=500)


class VisionExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')

    candidates: list[VisionCandidate] = Field(max_length=4)
    needs_review: bool


class VisionProvider(Protocol):
    def extract(
        self,
        image: bytes,
        content_type: str,
        location: str,
    ) -> VisionExtraction:
        ...


class NebiusVisionProvider:
    def __init__(
        self,
        client=None,
        model: str = 'openbmb/MiniCPM-V-4_5',
    ):
        if client is None:
            load_local_environment()

            from openai import OpenAI

            key = os.environ.get('NEBIUS_API_KEY')
            if not key:
                raise ValueError('NEBIUS_API_KEY is required')

            client = OpenAI(
                base_url='https://api.tokenfactory.nebius.com/v1/',
                api_key=key,
                timeout=30.0,
                max_retries=1,
            )

        self._client = client
        self._model = model

    def extract(
        self,
        image: bytes,
        content_type: str,
        location: str,
    ) -> VisionExtraction:
        if (
            not image
            or len(image) > MAX_IMAGE_BYTES
            or detected_image_type(image) != content_type
        ):
            raise ValueError('Unsupported image content')

        if not location.strip():
            raise ValueError('Location is required')

        encoded = base64.b64encode(image).decode('ascii')

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Inspect the image and report ONLY household conditions '
                        'whose target objects or areas are directly visible. '

                        'Return only a JSON object with exactly the keys '
                        'candidates and needs_review. '

                        'Each candidate must contain exactly category, value, '
                        'location, visible_evidence. '

                        'Allowed categories: dish_load, laundry_load, '
                        'plant_condition, lawn_condition. '

                        'For dish_load, the sink or dishes must be visible; '
                        'an empty visible sink has value 0. '

                        'For laundry_load, the laundry basket or laundry pile '
                        'must be visible. '

                        'For plant_condition, a plant must be visible. '

                        'For lawn_condition, a lawn or grass area must be visible. '

                        'A missing or out-of-frame target is UNKNOWN, not zero; '
                        'omit that category entirely. '

                        'Never return all categories by default. '

                        'The visible_evidence field must briefly identify '
                        'the actual visible object and condition, '
                        'not a guess about unseen areas. '

                        'Values range from 0 (empty load or healthy visible '
                        'condition) to 1 (extremely high load or unhealthy). '

                        'For dish_load, estimate VISIBLE dishwashing WORKLOAD, '
                        'not a binary dirty/not-dirty flag or sink occupancy '
                        'percentage. '

                        'Consider the visible number and type of dishes, pots, '
                        'pans, utensils, and apparent food residue, without '
                        'assuming hidden dirt or unseen items. '

                        'Use this dish_load scale: '
                        '0.0 = clearly empty or no dishes needing washing; '
                        '0.01 to 0.25 = very light, one or two ordinary items; '
                        '0.26 to 0.50 = light to moderate, several items; '
                        '0.51 to 0.75 = substantial, multiple dirty items '
                        'or cookware; '
                        '0.76 to 0.99 = heavy, many dirty items or difficult '
                        'cookware; '
                        '1.0 = extreme visible dishwashing workload only. '

                        'Do not assign 1.0 merely because any dirty dish '
                        'is visible. '

                        'These ranges are qualitative guidance, '
                        'not item-count formulas. '

                        'Use the provided location verbatim. '

                        'If no supported condition can be observed, or '
                        'visibility is too ambiguous to judge, return '
                        '{"candidates": [], "needs_review": true}. '

                        'Otherwise return needs_review false. '
                        'Never provide a confidence score.'
                    ),
                },
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'text',
                            'text': f'Location: {location}',
                        },
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': (
                                    f'data:{content_type};base64,{encoded}'
                                ),
                            },
                        },
                    ],
                },
            ],
        )

        if (
            not response.choices
            or not isinstance(
                response.choices[0].message.content,
                str,
            )
        ):
            raise ValueError('Vision provider returned no text')

        raw = response.choices[0].message.content.strip()

        try:
            result = VisionExtraction.model_validate(json.loads(raw))
        except (ValueError, ValidationError) as exc:
            raise ValueError('Invalid vision provider response') from exc

        if (
            (not result.candidates and not result.needs_review)
            or (result.candidates and result.needs_review)
        ):
            raise ValueError('Inconsistent vision review status')

        for candidate in result.candidates:
            if candidate.location != location:
                raise ValueError(
                    f'Vision location mismatch: expected {location!r}, '
                    f'received {candidate.location!r}'
                )

            if candidate.category == ConditionType.MAINTENANCE_STATUS:
                raise ValueError(
                    'Vision provider returned unsupported category'
                )

            if not candidate.visible_evidence.strip():
                raise ValueError(
                    'Vision provider returned empty visual evidence'
                )

        if len({
            candidate.category for candidate in result.candidates
        }) != len(result.candidates):
            raise ValueError('Duplicate vision categories')

        return result


class VisionService:
    def __init__(
        self,
        media: MediaService,
        provider: VisionProvider,
    ):
        self._media = media
        self._provider = provider

    def inspect_image(
        self,
        household_id: str,
        media_id: str,
        location: str,
    ) -> VisionExtraction | None:
        media = self._media.get_image(household_id, media_id)

        if media is None:
            return None

        info, image = media

        return self._provider.extract(
            image,
            info.content_type,
            location,
        )

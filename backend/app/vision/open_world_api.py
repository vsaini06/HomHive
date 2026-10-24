
"""Explicit, opt-in live open-world preview, no database mutations."""

import hmac
import logging
from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from app.services.open_world_live import preview_verified_scene


logger = logging.getLogger(__name__)


def build_open_world_preview_router(
    media,
    household_tokens: Mapping[str, str],
    build_pipeline,
):
    router = APIRouter(
        prefix="/households/{household_id}/media",
        tags=["open-world-preview"],
    )
    bearer = HTTPBearer(auto_error=False)

    @router.post("/{media_id}/open-world-preview")
    def preview(
        household_id: str,
        media_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        expected = household_tokens.get(household_id)

        if (
            expected is None
            or credentials is None
            or not hmac.compare_digest(credentials.credentials, expected)
        ):
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )

        stored = media.get_image(household_id, media_id)

        if stored is None:
            raise HTTPException(
                status_code=404,
                detail="Media not found",
            )

        info, image = stored
        independent = None

        try:
            vision, planner, reviewer = build_pipeline()
            independent = getattr(vision, "independent", None)

            outcome = preview_verified_scene(
                image=image,
                media_type=info.content_type,
                media_id=media_id,
                vision=vision,
                planner=planner,
                reviewer=reviewer,
            )

        except Exception as exc:
            if isinstance(exc, ValidationError):
                diagnostics = [
                    {
                        "field": ".".join(map(str, error["loc"])),
                        "type": error["type"],
                    }
                    for error in exc.errors(include_input=False)
                ]

                logger.warning(
                    "Open-world schema validation failed: fields=%s",
                    diagnostics,
                )
            else:
                logger.warning(
                    "Open-world preview incomplete: error_type=%s",
                    type(exc).__name__,
                )

            raise HTTPException(
                status_code=503,
                detail="Open-world verification incomplete; no results saved",
            ) from exc

        finally:
            if independent is not None and hasattr(independent.client, "close"):
                independent.client.close()

        return outcome.model_dump(mode="json")

    return router

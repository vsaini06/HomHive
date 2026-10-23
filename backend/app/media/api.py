import hmac
from uuid import uuid4
from app.evidence import EvidenceInput
from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import Response

from .service import MAX_IMAGE_BYTES, MediaService, detected_image_type


def build_media_router(service: MediaService, household_tokens: Mapping[str, str], observation_processor=None, evidence_ingestion=None) -> APIRouter:
    router = APIRouter(prefix='/households/{household_id}/media', tags=['media'])
    bearer = HTTPBearer(auto_error=False)

    def authorize(household_id: str, credentials: HTTPAuthorizationCredentials | None) -> None:
        token = household_tokens.get(household_id)
        if (
            token is None or credentials is None
            or not hmac.compare_digest(credentials.credentials, token)
        ):
            raise HTTPException(status_code=403, detail='Access denied')

    @router.post('', status_code=201)
    async def upload_image(household_id: str, file: UploadFile, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), location: str | None = Form(default=None), event_id: str | None = Form(default=None), defer_analysis: bool = Form(default=False)):
        authorize(household_id, credentials)
        if file.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
            raise HTTPException(status_code=415, detail='Unsupported image type')
        data = await file.read(MAX_IMAGE_BYTES + 1)
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail='Invalid image size')
        if detected_image_type(data) != file.content_type:
            raise HTTPException(status_code=415, detail='Image content does not match declared type')
        if evidence_ingestion is not None:
            try:
                response = evidence_ingestion.ingest(household_id, EvidenceInput(
                    source_id='phone-upload', source_type='phone',
                    event_id=event_id or str(uuid4()), content=data,
                    content_type=file.content_type, location_hint=location,
                ), defer_processing=defer_analysis)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            response['size_bytes'] = len(data)
            return response
        info = service.save_image(household_id, data)
        response = {'id': info.id, 'content_type': info.content_type, 'size_bytes': info.size_bytes}
        if observation_processor is not None and not defer_analysis:
            # A room label supplied by the user is context, not inferred identity.
            # Unknown is explicit when no location has been verified.
            resolved_location = (location or '').strip() or 'unknown'
            try:
                outcome = observation_processor.extract_and_store(household_id, info.id, resolved_location)
                if outcome is None:
                    response['processing'] = 'unavailable'
                else:
                    result, observations = outcome
                    response['processing'] = 'needs_review' if result.needs_review else 'processed'
                    response['observations'] = [o.model_dump(mode='json') for o in observations]
            except Exception:
                # The uploaded evidence remains persisted and can be retried by
                # the existing extraction endpoint. Never expose provider errors.
                response['processing'] = 'retry_required'
        if defer_analysis:
            response['processing'] = 'received'
        return response

    @router.get('/{media_id}')
    def get_image(household_id: str, media_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        authorize(household_id, credentials)
        result = service.get_image(household_id, media_id)
        if result is None:
            raise HTTPException(status_code=404, detail='Media not found')
        info, data = result
        return Response(data, media_type=info.content_type, headers={'Cache-Control': 'private, no-store'})

    return router

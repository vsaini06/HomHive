import hmac
from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import Response

from .service import MAX_IMAGE_BYTES, MediaService, detected_image_type


def build_media_router(service: MediaService, household_tokens: Mapping[str, str]) -> APIRouter:
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
    async def upload_image(household_id: str, file: UploadFile, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        authorize(household_id, credentials)
        if file.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
            raise HTTPException(status_code=415, detail='Unsupported image type')
        data = await file.read(MAX_IMAGE_BYTES + 1)
        if not data or len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail='Invalid image size')
        if detected_image_type(data) != file.content_type:
            raise HTTPException(status_code=415, detail='Image content does not match declared type')
        info = service.save_image(household_id, data)
        return {'id': info.id, 'content_type': info.content_type, 'size_bytes': info.size_bytes}

    @router.get('/{media_id}')
    def get_image(household_id: str, media_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        authorize(household_id, credentials)
        result = service.get_image(household_id, media_id)
        if result is None:
            raise HTTPException(status_code=404, detail='Media not found')
        info, data = result
        return Response(data, media_type=info.content_type, headers={'Cache-Control': 'private, no-store'})

    return router

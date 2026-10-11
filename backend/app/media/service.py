from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.db.media_record import MediaRecord
from .storage import MediaStorage

MAX_IMAGE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class MediaInfo:
    id: str
    household_id: str
    content_type: str
    size_bytes: int
    created_at: datetime


def detected_image_type(content: bytes) -> str | None:
    if content.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return 'image/webp'
    return None


class MediaService:
    def __init__(self, sessions: sessionmaker[Session], storage: MediaStorage):
        self._sessions = sessions
        self._storage = storage

    def save_image(self, household_id: str, content: bytes) -> MediaInfo:
        if not content or len(content) > MAX_IMAGE_BYTES:
            raise ValueError('Invalid image size')
        content_type = detected_image_type(content)
        if content_type is None:
            raise ValueError('Unsupported image content')
        info = MediaInfo(str(uuid4()), household_id, content_type, len(content), datetime.now(timezone.utc))
        self._storage.store(household_id, info.id, content)
        try:
            with self._sessions.begin() as session:
                session.add(MediaRecord(**info.__dict__))
        except BaseException:
            self._storage.delete(household_id, info.id)
            raise
        return info

    def get_image(self, household_id: str, media_id: str) -> tuple[MediaInfo, bytes] | None:
        with self._sessions() as session:
            record = session.get(MediaRecord, (household_id, media_id))
            if record is None:
                return None
            info = MediaInfo(record.id, record.household_id, record.content_type, record.size_bytes, record.created_at)
        return info, self._storage.read(household_id, media_id)

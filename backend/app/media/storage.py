from pathlib import Path
from typing import Protocol
from uuid import UUID
import os


class MediaStorage(Protocol):
    def store(self, household_id: str, media_id: str, content: bytes) -> None: ...
    def read(self, household_id: str, media_id: str) -> bytes: ...
    def delete(self, household_id: str, media_id: str) -> None: ...


class LocalMediaStorage:
    def __init__(self, root: Path):
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, household_id: str, media_id: str) -> Path:
        UUID(media_id)
        if not household_id or len(household_id) > 128 or not all(
            character.isascii() and (character.isalnum() or character in '_-')
            for character in household_id
        ):
            raise ValueError('Invalid household ID')
        return self._root / household_id / media_id

    def store(self, household_id: str, media_id: str, content: bytes) -> None:
        path = self._path(household_id, media_id)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open('xb') as destination:
            destination.write(content)
        if os.name != 'nt':
            path.chmod(0o600)

    def read(self, household_id: str, media_id: str) -> bytes:
        return self._path(household_id, media_id).read_bytes()

    def delete(self, household_id: str, media_id: str) -> None:
        self._path(household_id, media_id).unlink(missing_ok=True)

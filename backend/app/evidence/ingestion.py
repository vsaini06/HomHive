"""Source-neutral, household-scoped ingestion of authorized image evidence.

An adapter supplies bytes and source provenance. This service never infers that
an observation was confirmed just because a model produced a prediction.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.evidence_record import EvidenceRecord
from app.media.service import MAX_IMAGE_BYTES, MediaService, detected_image_type


@dataclass(frozen=True)
class EvidenceInput:
    source_id: str
    source_type: str
    event_id: str
    content: bytes
    content_type: str
    captured_at: datetime | None = None
    location_hint: str | None = None
    consent_reference: str | None = None


class EvidenceSource(Protocol):
    """Authorized input adapters implement this, with no device SDK dependency."""

    def fetch(self) -> EvidenceInput: ...


class EvidenceIngestion:
    def __init__(self, sessions: sessionmaker[Session], media: MediaService, processor=None):
        self._sessions = sessions
        self._media = media
        self._processor = processor

    def ingest(self, household_id: str, evidence: EvidenceInput, *, defer_processing: bool = False) -> dict:
        if (not household_id or not evidence.source_id or not evidence.event_id
                or len(evidence.source_id) > 128 or len(evidence.event_id) > 128):
            raise ValueError('Household, source and event identifiers are required')
        if not evidence.source_type:
            raise ValueError('Evidence source type is required')
        if (not evidence.content or len(evidence.content) > MAX_IMAGE_BYTES
                or detected_image_type(evidence.content) != evidence.content_type):
            raise ValueError('Unsupported image content')
        if evidence.captured_at and evidence.captured_at.tzinfo is None:
            raise ValueError('Capture timestamp needs timezone')
        digest = sha256(evidence.content).hexdigest()
        identity = (household_id, evidence.source_id, evidence.event_id)
        with self._sessions() as session:
            existing = session.get(EvidenceRecord, identity)
            if existing is not None:
                if existing.content_sha256 != digest:
                    raise ValueError('Repeated source event has changed content')
                return self._result(existing, duplicate=True)

        info = self._media.save_image(household_id, evidence.content)
        record = EvidenceRecord(
            household_id=household_id, source_id=evidence.source_id,
            event_id=evidence.event_id, evidence_id=str(uuid4()),
            source_type=evidence.source_type, media_id=info.id,
            content_type=evidence.content_type, content_sha256=digest,
            captured_at=evidence.captured_at,
            received_at=datetime.now(timezone.utc),
            location_hint=(evidence.location_hint or '').strip() or None,
            consent_reference=evidence.consent_reference,
            processing_status='received', processing_attempts=0,
            processing_updated_at=datetime.now(timezone.utc),
        )
        try:
            with self._sessions.begin() as session:
                session.add(record)
                session.flush()
        except IntegrityError:
            # Another worker won the same event ID. It owns processing.
            with self._sessions() as session:
                existing = session.get(EvidenceRecord, identity)
                if existing is None or existing.content_sha256 != digest:
                    raise ValueError('Conflicting event identifiers')
                return self._result(existing, duplicate=True)
        if defer_processing:
            response = self._result(record, duplicate=False)
            response["observations"] = []
            return response
        return self._process(household_id, identity)

    def retry(self, household_id: str, source_id: str, event_id: str) -> dict:
        identity = (household_id, source_id, event_id)
        with self._sessions() as session:
            record = session.get(EvidenceRecord, identity)
            if record is None:
                raise ValueError('Evidence not found')
            stale = (record.processing_status == 'processing' and
                (datetime.now(timezone.utc) - (record.processing_updated_at.replace(tzinfo=timezone.utc)
                 if record.processing_updated_at.tzinfo is None else record.processing_updated_at))
                 >= timedelta(minutes=15))
            if record.processing_status not in {'retry_required', 'received', 'pending_provider'} and not stale:
                return self._result(record, duplicate=True)
            if record.processing_attempts >= 3:
                return self._result(record, duplicate=True)
        return self._process(household_id, identity)

    def _process(self, household_id: str, identity: tuple[str, str, str]) -> dict:
        with self._sessions.begin() as session:
            record = session.get(EvidenceRecord, identity)
            record.processing_attempts += 1
            record.processing_status = 'processing'
            record.processing_updated_at = datetime.now(timezone.utc)
            media_id = record.media_id
            location = record.location_hint or 'unknown'
        if self._processor is None:
            status, observations = 'pending_provider', []
        else:
            try:
                result = self._processor.extract_and_store(household_id, media_id, location)
                if result is None:
                    status, observations = 'retry_required', []
                else:
                    extraction, observations = result
                    status = 'needs_review' if extraction.needs_review else 'processed'
            except Exception:
                status, observations = 'retry_required', []
        with self._sessions.begin() as session:
            record = session.get(EvidenceRecord, identity)
            record.processing_status = status
            record.processing_updated_at = datetime.now(timezone.utc)
        response = self._result(record, duplicate=False)
        response['observations'] = [o.model_dump(mode='json') for o in observations]
        return response

    @staticmethod
    def _result(record: EvidenceRecord, *, duplicate: bool) -> dict:
        return {'id': record.media_id, 'evidence_id': record.evidence_id,
                'source_type': record.source_type, 'processing': record.processing_status,
                'duplicate': duplicate, 'content_type': record.content_type}

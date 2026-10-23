from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.evidence_record import EvidenceRecord
from app.db.media_record import MediaRecord
from app.evidence import EvidenceIngestion, EvidenceInput
from app.media.api import build_media_router
from app.media.service import MediaService
from app.media.storage import LocalMediaStorage
from app.vision.provider import VisionExtraction

PNG = b'\x89PNG\r\n\x1a\n' + b'valid-fixture'


def setup_storage(tmp_path, processor=None):
    engine = create_engine(f'sqlite+pysqlite:///{tmp_path / "evidence.db"}')
    Base.metadata.create_all(engine, tables=[MediaRecord.__table__, EvidenceRecord.__table__])
    sessions = sessionmaker(engine, expire_on_commit=False)
    media = MediaService(sessions, LocalMediaStorage(tmp_path / 'media'))
    return engine, sessions, media, EvidenceIngestion(sessions, media, processor)


def test_independent_source_adapters_same_pipeline_and_tenant_isolation(tmp_path):
    class Extractor:
        calls = []
        def extract_and_store(self, household, media_id, location):
            self.calls.append((household, media_id, location))
            return VisionExtraction(candidates=[], needs_review=True), []
    processor = Extractor()
    engine, sessions, media, service = setup_storage(tmp_path, processor)
    class PhoneAdapter:
        def fetch(self):
            return EvidenceInput('phone-1', 'phone', 'capture-1', PNG, 'image/png')
    class FutureAdapterMock:
        def fetch(self):
            return EvidenceInput('authorized-test-source', 'test', 'event-9', PNG, 'image/png',
                captured_at=datetime.now(timezone.utc), location_hint='kitchen', consent_reference='test-consent')
    first = service.ingest('home', PhoneAdapter().fetch())
    second = service.ingest('home', FutureAdapterMock().fetch())
    assert first['processing'] == second['processing'] == 'needs_review'
    assert first['id'] != second['id']
    assert len(processor.calls) == 2
    assert service.ingest('home', PhoneAdapter().fetch())['duplicate'] is True
    assert len(processor.calls) == 2
    third = service.ingest('other-home', PhoneAdapter().fetch())
    assert third['id'] not in (first['id'], second['id'])
    with sessions() as session:
        assert len(session.scalars(select(EvidenceRecord)).all()) == 3
        assert session.get(EvidenceRecord, ('home', 'authorized-test-source', 'event-9')).consent_reference == 'test-consent'
    engine.dispose()


def test_source_event_content_collision_rejected(tmp_path):
    engine, _, _, service = setup_storage(tmp_path)
    item = EvidenceInput('device', 'phone', 'event', PNG, 'image/png')
    service.ingest('home', item)
    from pytest import raises
    with raises(ValueError, match='changed content'):
        service.ingest('home', EvidenceInput('device', 'phone', 'event', PNG + b'changed', 'image/png'))
    engine.dispose()


def test_failure_persists_for_retry_and_bounded_attempts(tmp_path):
    class Broken:
        def extract_and_store(self, *args):
            raise RuntimeError('secret error')
    engine, sessions, _, service = setup_storage(tmp_path, Broken())
    data = EvidenceInput('phone', 'phone', 'retry-id', PNG, 'image/png')
    first = service.ingest('home', data)
    assert first['processing'] == 'retry_required'
    for _ in range(3):
        service.retry('home', 'phone', 'retry-id')
    with sessions() as session:
        row = session.get(EvidenceRecord, ('home', 'phone', 'retry-id'))
        assert row.processing_attempts == 3
        assert row.processing_status == 'retry_required'
    engine.dispose()


def test_authorized_upload_uses_source_independent_ingestion(tmp_path):
    engine, sessions, media, ingest = setup_storage(tmp_path)
    app = FastAPI()
    app.include_router(build_media_router(media, {'home': 'token'}, None, ingest))
    with TestClient(app) as client:
        path = '/households/home/media'
        body = {'file': ('sample.png', PNG, 'image/png')}
        assert client.post(path, files=body).status_code == 403
        first = client.post(path, headers={'Authorization':'Bearer token'}, files=body,
                            data={'event_id':'same-event'})
        assert first.status_code == 201
        assert first.json()['processing'] == 'pending_provider'
        again = client.post(path, headers={'Authorization':'Bearer token'}, files=body,
                            data={'event_id':'same-event'})
        assert again.status_code == 201
        assert again.json()['duplicate'] is True
        assert first.json()['id'] == again.json()['id']
    engine.dispose()

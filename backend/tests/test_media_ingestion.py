from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.media_record import MediaRecord
from app.media.api import build_media_router
from app.media.service import MediaService
from app.media.storage import LocalMediaStorage

PNG = b'\x89PNG\r\n\x1a\n' + b'image-content'


def test_household_media_requires_authorization_and_persists_metadata(tmp_path):
    engine = create_engine(f'sqlite+pysqlite:///{tmp_path / "media.sqlite"}')
    Base.metadata.create_all(engine, tables=[MediaRecord.__table__])
    sessions = sessionmaker(engine, expire_on_commit=False)
    storage = LocalMediaStorage(tmp_path / 'private')
    app = FastAPI()
    app.include_router(build_media_router(MediaService(sessions, storage), {'home_one': 'one-secret', 'home_two': 'two-secret'}))
    with TestClient(app) as client:
        url = '/households/home_one/media'
        assert client.post(url, files={'file': ('photo.png', PNG, 'image/png')}).status_code == 403
        response = client.post(url, headers={'Authorization': 'Bearer one-secret'}, files={'file': ('photo.png', PNG, 'image/png')})
        assert response.status_code == 201
        media_id = response.json()['id']
        assert response.json()['size_bytes'] == len(PNG)
        assert client.get(f'{url}/{media_id}', headers={'Authorization': 'Bearer two-secret'}).status_code == 403
        assert client.get(f'/households/home_two/media/{media_id}', headers={'Authorization': 'Bearer two-secret'}).status_code == 404
        with sessions() as session:
            record = session.get(MediaRecord, ('home_one', media_id))
            assert record is not None
            assert record.content_type == 'image/png'
        result = client.get(f'{url}/{media_id}', headers={'Authorization': 'Bearer one-secret'})
        assert result.status_code == 200
        assert result.content == PNG
        assert result.headers['cache-control'] == 'private, no-store'
    engine.dispose()


def test_media_upload_rejects_invalid_content_and_oversized_files(tmp_path):
    engine = create_engine('sqlite+pysqlite:///:memory:')
    Base.metadata.create_all(engine, tables=[MediaRecord.__table__])
    service = MediaService(sessionmaker(engine), LocalMediaStorage(tmp_path))
    app = FastAPI()
    app.include_router(build_media_router(service, {'home': 'secret'}))
    with TestClient(app) as client:
        url = '/households/home/media'
        headers = {'Authorization': 'Bearer secret'}
        assert client.post(url, headers=headers, files={'file': ('bad.png', b'wrong', 'image/png')}).status_code == 415
        assert client.post(url, headers=headers, files={'file': ('oversize.png', PNG + b'x' * (10 * 1024 * 1024), 'image/png')}).status_code == 413
        assert client.post(url, headers=headers, files={'file': ('text.txt', b'text', 'text/plain')}).status_code == 415
    engine.dispose()


def test_failed_metadata_transaction_removes_stored_file(tmp_path):
    from pytest import raises
    from sqlalchemy.exc import OperationalError

    engine = create_engine('sqlite+pysqlite:///:memory:')
    sessions = sessionmaker(engine)
    storage = LocalMediaStorage(tmp_path / 'private')
    service = MediaService(sessions, storage)
    with raises(OperationalError):
        service.save_image('home', PNG)
    assert not list((tmp_path / 'private' / 'home').iterdir())
    engine.dispose()


def test_media_is_retrievable_with_a_new_service_instance(tmp_path):
    engine = create_engine(f'sqlite+pysqlite:///{tmp_path / "media.sqlite"}')
    Base.metadata.create_all(engine, tables=[MediaRecord.__table__])
    sessions = sessionmaker(engine, expire_on_commit=False)
    root = tmp_path / 'private'
    saved = MediaService(sessions, LocalMediaStorage(root)).save_image('home', PNG)
    restored = MediaService(sessions, LocalMediaStorage(root)).get_image('home', saved.id)
    assert restored is not None
    assert restored[0].id == saved.id
    assert restored[1] == PNG
    engine.dispose()


def test_media_operations_expose_http_bearer_security():
    app = FastAPI()
    app.include_router(build_media_router(None, {'home': 'secret'}))
    schema = app.openapi()
    schemes = schema['components']['securitySchemes']
    assert any(scheme == {'type': 'http', 'scheme': 'bearer'} for scheme in schemes.values())
    for path, method in (('/households/{household_id}/media', 'post'), ('/households/{household_id}/media/{media_id}', 'get')):
        requirements = schema['paths'][path][method]['security']
        assert any(any(name in schemes for name in entry) for entry in requirements)


def test_media_rejects_invalid_bearer_tokens(tmp_path):
    engine = create_engine(f'sqlite+pysqlite:///{tmp_path / "auth.sqlite"}')
    Base.metadata.create_all(engine, tables=[MediaRecord.__table__])
    service = MediaService(sessionmaker(engine), LocalMediaStorage(tmp_path))
    app = FastAPI()
    app.include_router(build_media_router(service, {'home': 'correct-token', 'other': 'different-token'}))
    with TestClient(app) as client:
        url = '/households/home/media'
        for headers in ({}, {'Authorization': 'Bearer wrong-token'}, {'Authorization': 'Basic correct-token'}, {'Authorization': 'Bearer different-token'}):
            response = client.post(url, headers=headers, files={'file': ('photo.png', PNG, 'image/png')})
            assert response.status_code == 403
        assert client.post(url, headers={'Authorization': 'Bearer correct-token'}, files={'file': ('photo.png', PNG, 'image/png')}).status_code == 201
    engine.dispose()

"""Local configuration loading remains predictable and isolated."""

import os

from app.config import environment


def test_backend_dotenv_is_loaded_from_an_explicit_path(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("HOMHIVE_TEST_ENV_SOURCE=from_file\n", encoding="utf-8")
    monkeypatch.setattr(environment, "_BACKEND_ENV_FILE", path)
    monkeypatch.setattr(environment, "_loaded", False)
    monkeypatch.delenv("HOMHIVE_TEST_ENV_SOURCE", raising=False)
    environment.load_local_environment()
    assert os.environ["HOMHIVE_TEST_ENV_SOURCE"] == "from_file"
    monkeypatch.delenv("HOMHIVE_TEST_ENV_SOURCE")
    environment.load_local_environment()
    assert "HOMHIVE_TEST_ENV_SOURCE" not in os.environ


def test_process_environment_overrides_dotenv(monkeypatch, tmp_path):
    path = tmp_path / ".env"
    path.write_text("HOMHIVE_TEST_ENV_OVERRIDE=from_file\n", encoding="utf-8")
    monkeypatch.setattr(environment, "_BACKEND_ENV_FILE", path)
    monkeypatch.setattr(environment, "_loaded", False)
    monkeypatch.setenv("HOMHIVE_TEST_ENV_OVERRIDE", "from_process")
    environment.load_local_environment()
    assert os.environ["HOMHIVE_TEST_ENV_OVERRIDE"] == "from_process"

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


def test_root_dotenv_fills_missing_values_but_backend_wins(monkeypatch, tmp_path):
    backend = tmp_path / "backend" / ".env"
    backend.parent.mkdir()
    backend.write_text("HOMHIVE_TEST_PRIORITY=backend\nHOMHIVE_TEST_BACKEND_ONLY=backend\n", encoding="utf-8")
    root = tmp_path / ".env"
    root.write_text("HOMHIVE_TEST_PRIORITY=root\nHOMHIVE_TEST_ROOT_ONLY=root\n", encoding="utf-8")
    monkeypatch.setattr(environment, "_BACKEND_ENV_FILE", backend)
    monkeypatch.setattr(environment, "_ROOT_ENV_FILE", root)
    monkeypatch.setattr(environment, "_loaded", False)
    for name in ("HOMHIVE_TEST_PRIORITY", "HOMHIVE_TEST_BACKEND_ONLY", "HOMHIVE_TEST_ROOT_ONLY"):
        monkeypatch.delenv(name, raising=False)
    environment.load_local_environment()
    assert os.environ["HOMHIVE_TEST_PRIORITY"] == "backend"
    assert os.environ["HOMHIVE_TEST_BACKEND_ONLY"] == "backend"
    assert os.environ["HOMHIVE_TEST_ROOT_ONLY"] == "root"


def test_process_variable_wins_over_both_files(monkeypatch, tmp_path):
    backend = tmp_path / "backend.env"
    root = tmp_path / "root.env"
    backend.write_text("HOMHIVE_TEST_PRECEDENCE=backend\n", encoding="utf-8")
    root.write_text("HOMHIVE_TEST_PRECEDENCE=root\n", encoding="utf-8")
    monkeypatch.setattr(environment, "_BACKEND_ENV_FILE", backend)
    monkeypatch.setattr(environment, "_ROOT_ENV_FILE", root)
    monkeypatch.setattr(environment, "_loaded", False)
    monkeypatch.setenv("HOMHIVE_TEST_PRECEDENCE", "process")
    environment.load_local_environment()
    assert os.environ["HOMHIVE_TEST_PRECEDENCE"] == "process"

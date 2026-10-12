"""Load local development configuration without overriding process settings."""

from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_loaded = False


def load_local_environment() -> None:
    """Load backend/.env at most once; explicitly configured variables win."""
    global _loaded
    if not _loaded:
        load_dotenv(dotenv_path=_BACKEND_ENV_FILE, override=False)
        _loaded = True

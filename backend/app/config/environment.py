"""Load local development configuration with explicit, stable precedence.

Highest to lowest: inherited process environment, backend/.env, project-root/.env.
Neither file is required in deployed environments, and no secrets are logged.
"""

from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_ROOT_ENV_FILE = _BACKEND_ENV_FILE.parent.parent / ".env"
_loaded = False


def load_local_environment() -> None:
    """Read both files once; never replace an explicit process value."""
    global _loaded
    if not _loaded:
        load_dotenv(dotenv_path=_BACKEND_ENV_FILE, override=False)
        load_dotenv(dotenv_path=_ROOT_ENV_FILE, override=False)
        _loaded = True

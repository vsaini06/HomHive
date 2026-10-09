"""Environment-based configuration for the optional persistence layer."""

import os


def get_database_url() -> str:
    """Read the connection URL when database functionality is requested.

    Importing the application must not require a database configuration.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ValueError(
            "DATABASE_URL is required for database operations; "
            "set it in your environment before running migrations."
        )
    return url

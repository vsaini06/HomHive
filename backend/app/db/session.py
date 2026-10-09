"""SQLAlchemy engine/session factory without implicit connection or transaction."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_database_url


def build_engine(database_url: str | None = None) -> Engine:
    """Build an engine lazily. This does not establish a DB connection."""
    return create_engine(database_url or get_database_url(), pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create independent sessions; consumers own transaction boundaries."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a session, rolling back failures and always closing it.

    Commit explicitly in the consuming repository/unit of work.
    """
    with factory() as session:
        try:
            yield session
        except BaseException:
            session.rollback()
            raise

"""Declarative metadata shared by SQLAlchemy persistence models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for ORM records; domain models remain independent."""

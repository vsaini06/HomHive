from datetime import datetime

from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ResearchCacheRecord(Base):
    __tablename__ = "research_cache"
    __table_args__ = (
        Index("ix_research_cache_household_expires", "household_id", "expires_at"),
    )

    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(48), nullable=False)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

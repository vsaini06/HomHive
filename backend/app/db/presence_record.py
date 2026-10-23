"""Household-scoped, user-controlled expiring presence signal."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class PresenceRecord(Base):
    __tablename__ = 'household_presence'
    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    signal_source: Mapped[str] = mapped_column(String(40), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    reliability: Mapped[float] = mapped_column(Float, nullable=False)
    consent_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

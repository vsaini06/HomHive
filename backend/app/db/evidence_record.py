"""Durable source provenance independent of observation trust status."""
from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class EvidenceRecord(Base):
    __tablename__ = 'evidence_ingestions'
    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_type: Mapped[str] = mapped_column(String(48), nullable=False)
    media_id: Mapped[str] = mapped_column(String(36), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    consent_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_attempts: Mapped[int] = mapped_column(Integer, nullable=False)

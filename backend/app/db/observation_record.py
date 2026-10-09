from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ObservationRecord(Base):
    __tablename__ = "observations"

    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[str] = mapped_column(String(48), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observation_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)

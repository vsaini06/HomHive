from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TaskRecord(Base):
    __tablename__ = "tasks"

    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_key: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_observation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False)
    estimated_effort_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    task_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)

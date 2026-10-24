"""Evidence-preserving autonomous-task lifecycle, independent of task vocabulary.

Inputs must already be independently corroborated and authorization must be checked
at the API boundary. An unverified room match can never close a task.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import JSON, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, Session, sessionmaker
from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskState(str, Enum):
    proposed = "proposed"
    pending = "pending"
    accepted = "accepted"
    in_progress = "in_progress"
    completed = "completed"
    dismissed = "dismissed"


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_id: str = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=1)
    original_image_reviewed: bool
    independent_review_passed: bool


class VerifiedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_key: str = Field(min_length=8, max_length=128)
    title: str = Field(min_length=3, max_length=250)
    action: str = Field(min_length=8, max_length=2000)
    observed_location: str | None = None
    action_location: str | None = None
    verification_criteria: str = Field(min_length=12, max_length=1000)
    evidence: EvidenceReference
    estimate_min: int | None = Field(default=None, ge=1)
    estimate_max: int | None = Field(default=None, ge=1)
    estimate_rationale: str | None = None
    confirmation_required: bool = False

    @model_validator(mode="after")
    def validate_evidence(self):
        if not self.evidence.original_image_reviewed or not self.evidence.independent_review_passed:
            raise ValueError("Cannot persist an action without independent media review")
        if (self.estimate_min is None) != (self.estimate_max is None):
            raise ValueError("Both effort bounds must be present or unknown")
        if self.estimate_min is not None and (self.estimate_min > self.estimate_max or not self.estimate_rationale):
            raise ValueError("Effort range needs order and grounding")
        return self


class RoomContinuity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    physical_room_id: str | None = None
    same_physical_room_verified: bool = False
    reason: str = Field(min_length=8)

    @model_validator(mode="after")
    def checked(self):
        if self.same_physical_room_verified and not self.physical_room_id:
            raise ValueError("A verified room match needs a stable physical room ID")
        return self


class OutcomeVerdict(str, Enum):
    completed = "completed"
    still_needed = "still_needed"
    partially_completed = "partially_completed"
    inconclusive = "inconclusive"


class ReviewedOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    verdict: OutcomeVerdict
    evidence: EvidenceReference
    criterion_verified: bool
    reviewer_explanation: str = Field(min_length=12)

    @model_validator(mode="after")
    def verified(self):
        if not self.evidence.original_image_reviewed or not self.evidence.independent_review_passed:
            raise ValueError("Completion verdict needs independent original-media review")
        if self.verdict == OutcomeVerdict.completed and not self.criterion_verified:
            raise ValueError("Completion requires proving the task criterion")
        return self


class AutonomousTaskRecord(Base):
    __tablename__ = "autonomous_tasks"
    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    physical_room_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    action: Mapped[str] = mapped_column(String(2000), nullable=False)
    criteria: Mapped[str] = mapped_column(String(1000), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    effort_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effort_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    task_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("household_id", "physical_room_id", "action_key", name="uq_autonomous_task_per_room"),
        Index("ix_autonomous_tasks_room", "household_id", "physical_room_id"),
    )


class AutonomousTaskEventRecord(Base):
    __tablename__ = "autonomous_task_events"
    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    household_id: Mapped[str] = mapped_column(String(128), nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    media_id: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["household_id", "task_id"], ["autonomous_tasks.household_id", "autonomous_tasks.id"]),
        Index("ix_autonomous_event_task", "household_id", "task_id", "created_at"),
        UniqueConstraint("household_id", "task_id", "media_id", "kind", name="uq_autonomous_event_once"),
    )


class AutonomousLifecycle:
    """Transactional task upserts and conservative evidence-based state changes.

    Caller authenticates household membership. Caller supplies independently verified
    room continuity; category alone must never be used as the physical_room_id.
    """
    def __init__(self, session_factory: sessionmaker[Session]):
        self.sessions = session_factory

    def _event(self, db: Session, task: AutonomousTaskRecord, media_id: str, kind: str, detail: dict):
        existing = db.scalar(select(AutonomousTaskEventRecord.event_id).where(
            AutonomousTaskEventRecord.household_id == task.household_id,
            AutonomousTaskEventRecord.task_id == task.id,
            AutonomousTaskEventRecord.media_id == media_id,
            AutonomousTaskEventRecord.kind == kind,
        ))
        if existing is None:
            db.add(AutonomousTaskEventRecord(event_id=str(uuid4()), household_id=task.household_id,
                task_id=task.id, media_id=media_id, kind=kind, detail=detail, created_at=utcnow()))

    def discover(self, household_id: str, room: RoomContinuity, actions: list[VerifiedAction]):
        """Create or preserve tasks; a repeat image cannot reset accepted/completed states."""
        if not household_id:
            raise ValueError("Missing household")
        if not room.same_physical_room_verified or not room.physical_room_id:
            return {"created": [], "existing": [], "held_for_room_identity": len(actions)}
        created, existing = [], []
        with self.sessions.begin() as db:
            for action in actions:
                record = db.scalar(select(AutonomousTaskRecord).where(
                    AutonomousTaskRecord.household_id == household_id,
                    AutonomousTaskRecord.physical_room_id == room.physical_room_id,
                    AutonomousTaskRecord.action_key == action.action_key).with_for_update())
                if record is None:
                    record = AutonomousTaskRecord(
                        household_id=household_id, id=str(uuid4()), physical_room_id=room.physical_room_id,
                        action_key=action.action_key, title=action.title, action=action.action,
                        criteria=action.verification_criteria, state=TaskState.proposed.value if action.confirmation_required else TaskState.pending.value,
                        effort_min=action.estimate_min, effort_max=action.estimate_max,
                        task_payload=action.model_dump(mode="json"), created_at=utcnow(), updated_at=utcnow())
                    db.add(record)
                    db.flush()
                    created.append(record.id)
                else:
                    existing.append(record.id)
                self._event(db, record, action.evidence.media_id, "discovery", {
                    "claim_ids": action.evidence.claim_ids, "confirmation_required": action.confirmation_required})
        return {"created": created, "existing": existing, "held_for_room_identity": 0}

    def verify_fresh_scene(self, household_id: str, room: RoomContinuity, verdicts: list[ReviewedOutcome]):
        """Conservatively reconcile tasks against a separately reviewed new image."""
        results = {}
        if not room.same_physical_room_verified or not room.physical_room_id:
            return {v.task_id: "held_unverified_room" for v in verdicts}
        with self.sessions.begin() as db:
            for verdict in verdicts:
                task = db.get(AutonomousTaskRecord, (household_id, verdict.task_id))
                if task is None or task.physical_room_id != room.physical_room_id:
                    results[verdict.task_id] = "unmatched_task_or_room"
                    continue
                source_media = task.task_payload["evidence"]["media_id"]
                if verdict.evidence.media_id == source_media:
                    results[task.id] = "requires_fresh_media"
                    continue
                self._event(db, task, verdict.evidence.media_id, "verification", {
                    "verdict": verdict.verdict.value, "criterion_verified": verdict.criterion_verified,
                    "reason": verdict.reviewer_explanation, "claim_ids": verdict.evidence.claim_ids})
                if task.state == TaskState.dismissed.value:
                    results[task.id] = "dismissed_unchanged"
                elif task.state == TaskState.completed.value:
                    results[task.id] = "completed_unchanged"
                elif verdict.verdict == OutcomeVerdict.completed and verdict.criterion_verified:
                    task.state = TaskState.completed.value
                    task.updated_at = utcnow()
                    results[task.id] = "completed"
                else:
                    results[task.id] = "kept_active"
        return results

    def list_tasks(self, household_id: str):
        with self.sessions() as db:
            records = db.scalars(select(AutonomousTaskRecord).where(
                AutonomousTaskRecord.household_id == household_id).order_by(AutonomousTaskRecord.created_at)).all()
            return [{"id": r.id, "room_id": r.physical_room_id, "title": r.title,
                     "action": r.action, "status": r.state, "effort_min": r.effort_min,
                     "effort_max": r.effort_max, "criteria": r.criteria} for r in records]

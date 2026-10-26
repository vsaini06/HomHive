"""Evidence-preserving autonomous-task lifecycle, independent of task vocabulary.

Inputs must already be independently corroborated and authorization must be checked
at the API boundary. An unverified room match can never close a task.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, time as day_time
from enum import Enum
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    room_category: str | None = Field(default=None, max_length=120)
    evidence_summary: str | None = Field(default=None, max_length=800)
    action_location: str | None = None
    verification_criteria: str = Field(min_length=12, max_length=1000)
    evidence: EvidenceReference
    estimate_min: int | None = Field(default=None, ge=1)
    estimate_max: int | None = Field(default=None, ge=1)
    estimate_rationale: str | None = None
    estimate_sources: list[str] = Field(default_factory=list, max_length=5)
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
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    next_step: str | None = Field(default=None, max_length=350)

    @model_validator(mode="after")
    def verified(self):
        if not self.evidence.original_image_reviewed or not self.evidence.independent_review_passed:
            raise ValueError("Completion verdict needs independent original-media review")
        if self.verdict == OutcomeVerdict.completed and not self.criterion_verified:
            raise ValueError("Completion requires proving the task criterion")
        if self.verdict == OutcomeVerdict.completed:
            if self.progress_percent is None:
                self.progress_percent = 100
            elif self.progress_percent != 100:
                raise ValueError("Verified completion requires 100 percent progress")
        if self.verdict == OutcomeVerdict.partially_completed and (
            self.progress_percent is None or not 0 < self.progress_percent < 100
        ):
            raise ValueError("Partial progress needs an evidence-supported estimate between 1 and 99")
        if self.verdict == OutcomeVerdict.inconclusive and self.progress_percent is not None:
            raise ValueError("Inconclusive photographs cannot establish progress")
        if self.verdict == OutcomeVerdict.still_needed and self.progress_percent == 100:
            raise ValueError("Unfinished tasks cannot be 100 percent complete")
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


class AutonomousAlertRecord(Base):
    __tablename__ = "autonomous_alerts"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    household_id: Mapped[str] = mapped_column(String(128), nullable=False)
    task_id: Mapped[str] = mapped_column(String(128), nullable=False)
    media_id: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    detail: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("household_id", "task_id", "media_id", "kind", name="uq_autonomous_alert_once"),
                      Index("ix_autonomous_alert_household", "household_id", "created_at"),)


class AutonomousAvailabilityRecord(Base):
    __tablename__ = "autonomous_availability"
    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    weekdays: Mapped[list] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def validated_availability(*, timezone_name: str, start_time: str, end_time: str, weekdays: list[int]):
    try:
        tz = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError("Choose a supported time zone") from None
    try:
        start = day_time.fromisoformat(start_time)
        end = day_time.fromisoformat(end_time)
    except (ValueError, TypeError):
        raise ValueError("Use a valid HH:MM time") from None
    if (start.strftime("%H:%M") != start_time or end.strftime("%H:%M") != end_time
            or start >= end):
        raise ValueError("Your daily window must start before it ends")
    if (not isinstance(weekdays, list) or not weekdays or
        any(type(day) is not int or day not in range(7) for day in weekdays)):
        raise ValueError("Select at least one weekday")
    return tz, start, end, sorted(set(weekdays))


def recommended_window(profile: dict | None, estimate_max: int | None, *, clock=None):
    """Suggest, never claim calendar availability; use only user-supplied recurring windows."""
    if profile is None or estimate_max is None:
        return None
    tz, start, end, days = validated_availability(
        timezone_name=profile["timezone"], start_time=profile["start_time"],
        end_time=profile["end_time"], weekdays=profile["weekdays"])
    current = (clock or utcnow()).astimezone(tz)
    for offset in range(8):
        date = (current + timedelta(days=offset)).date()
        if date.weekday() not in days:
            continue
        beginning = datetime.combine(date, start, tzinfo=tz)
        ending = datetime.combine(date, end, tzinfo=tz)
        candidate = max(current, beginning) if offset == 0 else beginning
        if candidate + timedelta(minutes=estimate_max) <= ending:
            return candidate.isoformat()
    return None


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

    def set_availability(self, household_id: str, *, timezone_name: str, start_time: str,
                         end_time: str, weekdays: list[int]):
        _, _, _, weekdays = validated_availability(timezone_name=timezone_name,
            start_time=start_time, end_time=end_time, weekdays=weekdays)
        with self.sessions.begin() as db:
            record = db.get(AutonomousAvailabilityRecord, household_id)
            if record is None:
                record = AutonomousAvailabilityRecord(household_id=household_id,
                    timezone=timezone_name, start_time=start_time, end_time=end_time,
                    weekdays=weekdays, updated_at=utcnow())
                db.add(record)
            else:
                record.timezone = timezone_name
                record.start_time = start_time
                record.end_time = end_time
                record.weekdays = weekdays
                record.updated_at = utcnow()
        return self.get_availability(household_id)

    def get_availability(self, household_id: str):
        with self.sessions() as db:
            item = db.get(AutonomousAvailabilityRecord, household_id)
            return ({"timezone": item.timezone, "start_time": item.start_time,
                     "end_time": item.end_time, "weekdays": item.weekdays}
                    if item else None)

    def alerts(self, household_id: str):
        with self.sessions() as db:
            rows = db.scalars(select(AutonomousAlertRecord).where(
                AutonomousAlertRecord.household_id == household_id)
                .order_by(AutonomousAlertRecord.created_at.desc()).limit(60)).all()
            return [{"id": row.id, "task_id": row.task_id, "kind": row.kind,
                     "title": row.title, "detail": row.detail,
                     "created_at": row.created_at.isoformat(),
                     "read_at": row.read_at.isoformat() if row.read_at else None} for row in rows]

    def read_alert(self, household_id: str, alert_id: str):
        with self.sessions.begin() as db:
            item = db.scalar(select(AutonomousAlertRecord).where(
                AutonomousAlertRecord.id == alert_id,
                AutonomousAlertRecord.household_id == household_id).with_for_update())
            if item is None:
                raise LookupError("Notification not found")
            item.read_at = item.read_at or utcnow()
            return {"id": item.id, "read_at": item.read_at.isoformat()}

    def _alert(self, db, task, media_id, kind, title, detail):
        previous = db.scalar(select(AutonomousAlertRecord.id).where(
            AutonomousAlertRecord.household_id == task.household_id,
            AutonomousAlertRecord.task_id == task.id,
            AutonomousAlertRecord.media_id == media_id,
            AutonomousAlertRecord.kind == kind))
        if previous is None:
            if kind == "suggestion":
                pref = db.get(AutonomousAvailabilityRecord, task.household_id)
                if pref is not None:
                    slot = recommended_window({"timezone": pref.timezone,
                        "start_time": pref.start_time, "end_time": pref.end_time,
                        "weekdays": pref.weekdays}, task.effort_max)
                    if slot:
                        local = datetime.fromisoformat(slot)
                        detail += (f" Suggested: {local.strftime('%a %I:%M %p')}"
                                   " within your preferred household-work window."
                                   " This is not verified calendar availability.")
            db.add(AutonomousAlertRecord(id=str(uuid4()), household_id=task.household_id,
                task_id=task.id, media_id=media_id, kind=kind, title=title[:250],
                detail=detail[:1000], created_at=utcnow()))

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
                    if not action.confirmation_required:
                        estimate = (f"Published-duration estimate: {action.estimate_min}–{action.estimate_max} minutes."
                                    if action.estimate_min is not None else "Duration not yet established.")
                        self._alert(db, record, action.evidence.media_id, "suggestion",
                            f"Suggested: {action.title}",
                            f"HomHive found independently supported household work. {estimate} No approval needed.")
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
                previous = db.scalar(select(AutonomousTaskEventRecord.event_id).where(
                    AutonomousTaskEventRecord.household_id == household_id,
                    AutonomousTaskEventRecord.task_id == task.id,
                    AutonomousTaskEventRecord.media_id == verdict.evidence.media_id,
                    AutonomousTaskEventRecord.kind == "verification"))
                if previous is not None:
                    results[task.id] = "already_reviewed"
                    continue
                self._event(db, task, verdict.evidence.media_id, "verification", {
                    "verdict": verdict.verdict.value, "criterion_verified": verdict.criterion_verified,
                    "reason": verdict.reviewer_explanation, "claim_ids": verdict.evidence.claim_ids,
                    "progress_percent": verdict.progress_percent, "next_step": verdict.next_step})
                if task.state == TaskState.dismissed.value:
                    results[task.id] = "dismissed_unchanged"
                elif task.state == TaskState.completed.value:
                    results[task.id] = "completed_unchanged"
                elif verdict.verdict == OutcomeVerdict.inconclusive:
                    results[task.id] = "kept_active"
                else:
                    payload = dict(task.task_payload)
                    if verdict.progress_percent is not None:
                        payload["progress"] = {
                            "percent": verdict.progress_percent, "media_id": verdict.evidence.media_id,
                            "explanation": verdict.reviewer_explanation[:750],
                            "next_step": verdict.next_step,
                            "reviewed_at": utcnow().isoformat(),
                            "estimated": verdict.verdict != OutcomeVerdict.completed,
                        }
                    if verdict.verdict == OutcomeVerdict.completed and verdict.criterion_verified:
                        task.state = TaskState.completed.value
                        results[task.id] = "completed"
                        self._alert(db, task, verdict.evidence.media_id, "completed",
                            f"Verified complete: {task.title}",
                            "A later photo of the same space supports the completion criteria.")
                    else:
                        # A fresh visual assessment can show progress or regression.
                        if verdict.progress_percent is not None and verdict.progress_percent > 0:
                            task.state = TaskState.in_progress.value
                            results[task.id] = "progress_updated"
                            self._alert(db, task, verdict.evidence.media_id, "progress",
                                f"Progress updated: {task.title}",
                                f"About {verdict.progress_percent}% complete based on the latest photograph. "
                                f"{(verdict.next_step or verdict.reviewer_explanation)[:400]}")
                        else:
                            if task.state == TaskState.in_progress.value:
                                task.state = TaskState.pending.value
                            results[task.id] = "still_needed"
                    task.task_payload = payload
                    task.updated_at = utcnow()
        return results

    def decide(self, household_id: str, task_id: str, decision: str):
        allowed = {"accept": TaskState.accepted.value, "decline": TaskState.dismissed.value,
                   "remind": TaskState.pending.value, "done": TaskState.in_progress.value}
        if decision not in allowed:
            raise ValueError("Unsupported task decision")
        with self.sessions.begin() as db:
            task = db.get(AutonomousTaskRecord, (household_id, task_id))
            if task is None:
                raise LookupError("Task not found")
            if task.state in (TaskState.completed.value, TaskState.dismissed.value):
                raise ValueError("This task is no longer actionable")
            if decision == "accept" and task.state not in (TaskState.pending.value, TaskState.proposed.value):
                raise ValueError("Task cannot be accepted in its current state")
            if decision == "done" and task.state not in (TaskState.pending.value, TaskState.accepted.value, TaskState.in_progress.value):
                raise ValueError("This task cannot be reported finished in its current state")
            if decision == "remind" and task.state not in (TaskState.proposed.value, TaskState.pending.value):
                raise ValueError("Only unaccepted suggestions can be snoozed")
            task.state = allowed[decision]
            task.updated_at = utcnow()
            payload = dict(task.task_payload)
            if decision == "remind":
                from datetime import timedelta
                payload["remind_at"] = (utcnow() + timedelta(minutes=30)).isoformat()
            elif decision == "done":
                payload["user_reported_done_at"] = utcnow().isoformat()
            else:
                payload.pop("remind_at", None)
            task.task_payload = payload
            self._event(db, task, f"user-decision:{task.id}:{decision}:{task.updated_at.isoformat()}",
                        "user_decision", {"decision": decision})
            return {"id": task.id, "status": task.state, "updated_at": task.updated_at.isoformat(),
                    "remind_at": payload.get("remind_at")}

    def list_tasks(self, household_id: str):
        with self.sessions() as db:
            pref = db.get(AutonomousAvailabilityRecord, household_id)
            profile = ({"timezone":pref.timezone, "start_time":pref.start_time,
                        "end_time":pref.end_time, "weekdays":pref.weekdays} if pref else None)
            records = db.scalars(select(AutonomousTaskRecord).where(
                AutonomousTaskRecord.household_id == household_id).order_by(AutonomousTaskRecord.created_at)).all()
            return [{"id": r.id, "room_id": r.physical_room_id, "title": r.title,
                     "action": r.action, "status": r.state, "effort_min": r.effort_min,
                     "effort_max": r.effort_max, "criteria": r.criteria,
                     "room_category": r.task_payload.get("room_category"),
                     "source_media_id": (r.task_payload.get("evidence") or {}).get("media_id"),
                     "evidence_summary": r.task_payload.get("evidence_summary"),
                     "created_at": r.created_at.isoformat(),
                     "updated_at": r.updated_at.isoformat(),
                     "remind_at": r.task_payload.get("remind_at"),
                     "estimate_rationale": r.task_payload.get("estimate_rationale"),
                     "estimate_sources": r.task_payload.get("estimate_sources", []),
                     "confirmation_required": r.task_payload.get("confirmation_required", False),
                     "progress": r.task_payload.get("progress"),
                     "recommended_at": recommended_window(profile, r.effort_max)
                         if r.state not in ("completed", "dismissed") else None,
                     "recommendation_basis": "preferred_window" if profile and r.effort_max else None,
                     } for r in records]

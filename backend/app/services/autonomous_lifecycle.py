"""Evidence-preserving autonomous-task lifecycle, independent of task vocabulary.

Inputs must already be independently corroborated and authorization must be checked
at the API boundary. An unverified room match can never close a task.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, time as day_time
from enum import Enum
import hashlib
import re
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import JSON, DateTime, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, Session, sessionmaker
from app.db.base import Base
from app.services.autonomous_objects import AutonomousObjectRecord, AutonomousObjectViewRecord


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
    physical_object_id: str | None = None
    same_physical_object_verified: bool = False
    reason: str = Field(min_length=8)

    @model_validator(mode="after")
    def checked(self):
        if self.same_physical_room_verified and not self.physical_room_id:
            raise ValueError("A verified room match needs a stable physical room ID")
        if self.same_physical_object_verified and not self.physical_object_id:
            raise ValueError("A verified object match needs a stable physical object ID")
        if self.same_physical_room_verified and self.same_physical_object_verified:
            raise ValueError("A task's verified subject must be either a room or an object")
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
        if self.verdict != OutcomeVerdict.completed and self.criterion_verified:
            raise ValueError("An uncompleted verdict cannot claim the task criterion is verified")
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
    physical_room_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
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
        UniqueConstraint("household_id", "object_id", "action_key", name="uq_autonomous_task_per_object"),
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


def _overlaps_existing_work(new_title: str, old_title: str) -> bool:
    """Conservative wording-independent overlap check within one verified room."""
    ignored = {'a', 'an', 'the', 'in', 'on', 'of', 'at', 'to', 'with', 'and', 'for',
               'from', 'all', 'into', 'off', 'up', 'your', 'these', 'those'}
    def words(title):
        return [w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in ignored]
    proposed, existing = words(new_title), words(old_title)
    if len(proposed) < 3 or len(existing) < 3 or proposed[0] != existing[0]:
        return False
    a, b = set(proposed), set(existing)
    overlap = len(a & b)
    return overlap >= 3 and overlap / min(len(a), len(b)) >= 0.8 and overlap / len(a | b) >= 0.5


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

    def task_timeline(self, household_id: str, task_id: str):
        """Household-scoped evidence and decisions for a particular task."""
        with self.sessions() as db:
            task = db.get(AutonomousTaskRecord, (household_id, task_id))
            if task is None:
                raise LookupError("Task not found")
            events = db.scalars(select(AutonomousTaskEventRecord).where(
                AutonomousTaskEventRecord.household_id == household_id,
                AutonomousTaskEventRecord.task_id == task_id)
                .order_by(AutonomousTaskEventRecord.created_at)).all()
            return {"task_id": task_id, "status": task.state, "events": [
                {"kind": event.kind, "media_id": event.media_id if not event.media_id.startswith("user-decision:") else None,
                 "detail": event.detail, "created_at": event.created_at.isoformat()}
                for event in events]}

    def household_pulse(self, household_id: str):
        """Proactive recommendations from persisted evidence, without invented conditions."""
        with self.sessions() as db:
            tasks = db.scalars(select(AutonomousTaskRecord).where(
                AutonomousTaskRecord.household_id == household_id)
                .order_by(AutonomousTaskRecord.created_at)).all()
            profile_row = db.get(AutonomousAvailabilityRecord, household_id)
            profile = ({"timezone": profile_row.timezone, "start_time": profile_row.start_time,
                        "end_time": profile_row.end_time, "weekdays": profile_row.weekdays}
                       if profile_row else None)
            findings = []
            for task in tasks:
                if task.state in (TaskState.completed.value, TaskState.dismissed.value):
                    continue
                payload = task.task_payload or {}
                progress = payload.get("progress") or {}
                history = db.scalars(select(AutonomousTaskEventRecord).where(
                    AutonomousTaskEventRecord.household_id == household_id,
                    AutonomousTaskEventRecord.task_id == task.id,
                    AutonomousTaskEventRecord.kind == "verification")
                    .order_by(AutonomousTaskEventRecord.created_at)).all()
                visible_count = sum(1 for event in history if event.detail.get("verdict") != "inconclusive")
                slot = recommended_window(profile, task.effort_max)
                missing_estimate = task.effort_max is None or len(payload.get("estimate_sources") or []) < 2
                created_at = task.created_at if task.created_at.tzinfo else task.created_at.replace(tzinfo=timezone.utc)
                age_days = max(0, int((utcnow() - created_at).total_seconds() // 86400))
                priority = min(100, 30 + min(age_days, 14) * 3 + (15 if visible_count >= 2 else 0)
                               + (10 if progress.get("percent", 0) and progress.get("percent", 0) < 100 else 0))
                reasons = ["Independently reviewed visual evidence"]
                if visible_count > 1:
                    reasons.append(f"Condition checked in {visible_count} follow-up photographs")
                if age_days >= 3:
                    reasons.append(f"Open for {age_days} days")
                findings.append({"task_id": task.id, "title": task.title, "room_id": task.physical_room_id,
                    "priority": priority, "reasons": reasons,
                    "progress_percent": progress.get("percent"),
                    "progress_explanation": progress.get("explanation"),
                    "remaining_work": progress.get("next_step"),
                    "follow_up_reviews": len(history), "recommended_at": slot,
                    "estimate_min": task.effort_min if not missing_estimate else None,
                    "estimate_max": task.effort_max if not missing_estimate else None,
                    "estimate_sources": payload.get("estimate_sources") or [],
                    "research_needed": missing_estimate, "status": task.state})
            findings.sort(key=lambda item: (-item["priority"], item["title"]))
            return {"active_count": len(findings), "verified_complete_count": sum(
                task.state == TaskState.completed.value for task in tasks),
                "work_window_configured": profile is not None,
                "suggestions": findings[:25]}

    def generate_due_reminders(self, *, clock=None):
        """Create at most one daily, household-scoped suggestion reminder per task.

        Never claim availability from a calendar: only the saved preferred time window.
        This method does not call AI providers and is safe to poll repeatedly.
        """
        moment = clock or utcnow()
        count = 0
        with self.sessions.begin() as db:
            profiles = db.scalars(select(AutonomousAvailabilityRecord)).all()
            for profile in profiles:
                tz, start, end, days = validated_availability(timezone_name=profile.timezone,
                    start_time=profile.start_time, end_time=profile.end_time, weekdays=profile.weekdays)
                local = moment.astimezone(tz)
                if local.weekday() not in days:
                    continue
                start_dt = datetime.combine(local.date(), start, tzinfo=tz)
                end_dt = datetime.combine(local.date(), end, tzinfo=tz)

                if not start_dt <= local < start_dt + timedelta(minutes=30):
                    continue
                tasks = db.scalars(select(AutonomousTaskRecord).where(
                    AutonomousTaskRecord.household_id == profile.household_id,
                    AutonomousTaskRecord.state.in_([TaskState.pending.value, TaskState.accepted.value,
                        TaskState.in_progress.value]))).all()
                for task in tasks:
                    if task.effort_max is None or local + timedelta(minutes=task.effort_max) > end_dt:
                        continue
                    if (task.task_payload or {}).get("remind_at") and moment < datetime.fromisoformat(task.task_payload["remind_at"]):
                        continue
                    dedupe_media = "preferred-window:" + local.date().isoformat()
                    exists = db.scalar(select(AutonomousAlertRecord.id).where(
                        AutonomousAlertRecord.household_id == profile.household_id,
                        AutonomousAlertRecord.task_id == task.id,
                        AutonomousAlertRecord.media_id == dedupe_media,
                        AutonomousAlertRecord.kind == "reminder"))
                    if exists:
                        continue
                    self._alert(db, task, dedupe_media, "reminder", f"A good time for: {task.title}",
                        f"Your preferred household-work window is open. Estimated duration: "
                        f"{task.effort_min}–{task.effort_max} minutes. "
                        "Check your real calendar before starting; availability isn't synchronized.")
                    count += 1
        return count

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
        object_scope = room.same_physical_object_verified and bool(room.physical_object_id)
        room_scope = room.same_physical_room_verified and bool(room.physical_room_id)
        if not (object_scope or room_scope):
            return {"created": [], "existing": [], "held_for_room_identity": len(actions)}
        created, existing = [], []
        with self.sessions.begin() as db:
            for action in actions:
                record = db.scalar(select(AutonomousTaskRecord).where(
                    AutonomousTaskRecord.household_id == household_id,
                    AutonomousTaskRecord.physical_room_id == (room.physical_room_id if room_scope else None),
                    AutonomousTaskRecord.object_id == (room.physical_object_id if object_scope else None),
                    AutonomousTaskRecord.action_key == action.action_key).with_for_update())
                persist_key = action.action_key
                if record is not None and record.state == TaskState.completed.value:
                    previous_media = (record.task_payload or {}).get('evidence', {}).get('media_id')
                    if previous_media != action.evidence.media_id:
                        suffix = hashlib.sha256(action.evidence.media_id.encode()).hexdigest()[:12]
                        persist_key = action.action_key[:115] + ':' + suffix
                        record = db.scalar(select(AutonomousTaskRecord).where(
                            AutonomousTaskRecord.household_id == household_id,
                            AutonomousTaskRecord.physical_room_id == (room.physical_room_id if room_scope else None),
                            AutonomousTaskRecord.object_id == (room.physical_object_id if object_scope else None),
                            AutonomousTaskRecord.action_key == persist_key).with_for_update())
                if record is None:
                    room_tasks = db.scalars(select(AutonomousTaskRecord).where(
                        AutonomousTaskRecord.household_id == household_id,
                        AutonomousTaskRecord.physical_room_id == (room.physical_room_id if room_scope else None),
                        AutonomousTaskRecord.object_id == (room.physical_object_id if object_scope else None),
                        AutonomousTaskRecord.state.in_([
                            TaskState.proposed.value, TaskState.pending.value,
                            TaskState.accepted.value, TaskState.in_progress.value]))).all()
                    record = next((existing_task for existing_task in room_tasks
                        if _overlaps_existing_work(action.title, existing_task.title)), None)
                if record is None:
                    record = AutonomousTaskRecord(
                        household_id=household_id, id=str(uuid4()),
                        physical_room_id=room.physical_room_id if room_scope else None,
                        object_id=room.physical_object_id if object_scope else None,
                        action_key=persist_key, title=action.title, action=action.action,
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
        object_scope = room.same_physical_object_verified and bool(room.physical_object_id)
        room_scope = room.same_physical_room_verified and bool(room.physical_room_id)
        if not (object_scope or room_scope):
            return {v.task_id: "held_unverified_room" for v in verdicts}
        with self.sessions.begin() as db:
            for verdict in verdicts:
                task = db.get(AutonomousTaskRecord, (household_id, verdict.task_id))
                if task is None or (task.object_id != room.physical_object_id if object_scope
                    else task.object_id is not None or task.physical_room_id != room.physical_room_id):
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
            from app.services.autonomous_objects import ObjectRegistry
            object_names = {o["id"]: o["name"] for o in ObjectRegistry(self.sessions).list(household_id)}
            return [{"id": r.id, "room_id": r.physical_room_id or f"object:{r.object_id}",
                     "object_id": r.object_id, "subject_type": "object" if r.object_id else "space",
                     "object_name": object_names.get(r.object_id) if r.object_id else None,
                     "title": r.title,
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
                     "automatic_guidance": r.task_payload.get("automatic_guidance"),
                     "observed_object": r.task_payload.get("observed_object"),
                     "confirmation_required": r.task_payload.get("confirmation_required", False),
                     "progress": r.task_payload.get("progress"),
                     "recommended_at": recommended_window(profile, r.effort_max)
                         if r.state not in ("completed", "dismissed") else None,
                     "recommendation_basis": "preferred_window" if profile and r.effort_max else None,
                     } for r in records]

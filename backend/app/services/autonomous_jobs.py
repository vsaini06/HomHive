"""Durable, opt-in image scan outbox; never invent room associations."""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, Index, select
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc)


class AutonomousRoomRecord(Base):
    __tablename__ = 'autonomous_rooms'
    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    reference_media_id: Mapped[str] = mapped_column(String(128), nullable=False)
    room_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    room_category_source: Mapped[str] = mapped_column(String(32), nullable=False, default="ai_reviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (UniqueConstraint('household_id','reference_media_id', name='uq_autonomous_room_reference'),)


class AutonomousScanJob(Base):
    __tablename__ = 'autonomous_scan_jobs'
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    household_id: Mapped[str] = mapped_column(String(128), nullable=False)
    media_id: Mapped[str] = mapped_column(String(128), nullable=False)
    room_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[str] = mapped_column(String(160), nullable=False, default='')
    review_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    __table_args__ = (UniqueConstraint('household_id','media_id',name='uq_autonomous_job_media'),
                     Index('ix_autonomous_job_pending','state','next_attempt_at'))


def _failure_summary(exc: Exception) -> str:
    """Error type and field paths only; never provider payloads, prompts or secrets."""
    errors = getattr(exc, 'errors', None)
    if callable(errors):
        try:
            fields = [".".join(map(str, e['loc'])) + ':' + e['type'] for e in errors(include_input=False)][:8]
            return f"{type(exc).__name__} {fields}"
        except Exception:
            pass
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    safe_errors = {
        "Planner response missing required actions field",
        "Planner actions must be an array",
        "Planner altered corroborated evidence or room provenance",
    }
    detail = str(exc) if type(exc) is ValueError and str(exc) in safe_errors else ''
    return " ".join(x for x in (type(exc).__name__, f"http={status}" if status else '', detail) if x)


def _user_failure_message(exc: Exception, *, retrying: bool) -> str:
    """Categorize failure without exposing prompts, provider bodies, or tokens."""
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    kind = type(exc).__name__.lower()
    message = str(exc) if type(exc) is ValueError else ''
    if status in {401, 403}:
        reason = 'The AI provider rejected its credentials. An administrator needs to check the connection.'
    elif status == 429:
        reason = 'The AI provider is busy or its usage limit was reached.'
    elif isinstance(status, int) and status >= 500:
        reason = 'The AI provider is temporarily unavailable.'
    elif 'timeout' in kind:
        reason = 'AI review timed out before it could finish.'
    elif 'connection' in kind or 'network' in kind:
        reason = 'The AI review service could not be reached.'
    elif 'validation' in kind or any(flag in message for flag in (
        'Planner response missing required actions field', 'Planner actions must be an array',
        'Planner altered corroborated evidence or room provenance')):
        reason = 'The AI response was incomplete or invalid, so HomHive did not create any tasks.'
    else:
        reason = 'AI review encountered a technical problem and could not finish.'
    return reason + (' A retry is scheduled.' if retrying else ' You can retry the saved photo.')


class AutonomousJobService:
    def __init__(self, sessions):
        self.sessions = sessions

    def enqueue(self, household_id: str, media_id: str):
        """Idempotent durable enqueue; unassigned media is held, not processed as a new room."""
        with self.sessions.begin() as db:
            existing = db.scalar(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id, AutonomousScanJob.media_id == media_id))
            if existing:
                return existing.id
            # Enrollment is explicit; worker performs independent room matching.
            jid = str(uuid4())
            db.add(AutonomousScanJob(id=jid, household_id=household_id, media_id=media_id,
                room_id=None, state='queued', attempts=0, next_attempt_at=now(), updated_at=now(), message=''))
            return jid

    def retry(self, household_id: str, media_id: str):
        """Allow an authorized user to retry held or failed work without duplicate jobs."""
        with self.sessions.begin() as db:
            job = db.scalar(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id,
                AutonomousScanJob.media_id == media_id).with_for_update())
            if job is None:
                raise LookupError("No job found for this photograph")
            if job.state in {"failed", "held_unverified_room"}:
                job.state = "queued"
                job.attempts = 0
                job.updated_at = now()
                job.next_attempt_at = now()
                job.message = ""
            return job.id

    def recheck_completed(self, household_id: str, media_id: str):
        """Only an authenticated, explicit request schedules another paid review."""
        with self.sessions.begin() as db:
            job = db.scalar(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id,
                AutonomousScanJob.media_id == media_id).with_for_update())
            if job is None:
                raise LookupError("No scan found")
            if job.state != 'completed':
                raise ValueError("Only completed scans can be re-reviewed")
            job.state = 'queued'
            job.attempts = 0
            job.next_attempt_at = now()
            job.updated_at = now()
            job.message = ''
            # Previous review evidence remains available until replaced, in case the retry fails.
            return job.id

    def correct_room_category(self, household_id: str, room_id: str, category: str):
        category = category.strip()
        if not 2 <= len(category) <= 120:
            raise ValueError("Space name must be between 2 and 120 characters")
        with self.sessions.begin() as db:
            room = db.get(AutonomousRoomRecord, (household_id, room_id))
            if room is None:
                raise LookupError("Space not found")
            room.room_category = category
            room.room_category_source = 'user_confirmed'
            return {'room_id': room.room_id, 'room_category': room.room_category,
                    'room_category_source': room.room_category_source}

    def enroll(self, household_id: str, media_id: str, room_category: str | None = None):
        with self.sessions.begin() as db:
            previous = db.scalar(select(AutonomousRoomRecord).where(
                AutonomousRoomRecord.household_id == household_id,
                AutonomousRoomRecord.reference_media_id == media_id))
            if previous:
                if room_category and not previous.room_category:
                    previous.room_category = room_category[:120]
                room_id = previous.room_id
            else:
                room_id = 'reference:' + media_id
                db.add(AutonomousRoomRecord(household_id=household_id, room_id=room_id,
                    reference_media_id=media_id, room_category=room_category[:120] if room_category else None,
                    room_category_source='ai_reviewed', created_at=now()))
            held = db.scalar(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id,
                AutonomousScanJob.media_id == media_id,
                AutonomousScanJob.state == 'held_unverified_room').with_for_update())
            if held is not None:
                held.state = 'queued'
                held.room_id = room_id
                held.attempts = 0
                held.next_attempt_at = now()
                held.updated_at = now()
                held.message = ''
            return room_id

    def rooms(self, household_id):
        with self.sessions() as db:
            rows = db.scalars(select(AutonomousRoomRecord).where(AutonomousRoomRecord.household_id == household_id)).all()
            return [{'room_id': r.room_id, 'reference_media_id': r.reference_media_id,
                     'room_category': r.room_category,
                     'room_category_source': r.room_category_source,
                     'created_at': r.created_at.isoformat()} for r in rows]

    def set_room_category(self, household_id: str, room_id: str, category: str | None):
        if not category:
            return
        with self.sessions.begin() as db:
            room = db.get(AutonomousRoomRecord, (household_id, room_id))
            if room and room.room_category_source != 'user_confirmed':
                room.room_category = category[:120]

    def jobs(self, household_id):
        with self.sessions() as db:
            rows = db.scalars(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id).order_by(AutonomousScanJob.updated_at.desc()).limit(100)).all()
            return [{'id':r.id,'media_id':r.media_id,'room_id':r.room_id,'state':r.state,
                'attempts':r.attempts,'message':r.message,
                'updated_at':r.updated_at.isoformat(),
                'review_summary':r.review_summary} for r in rows]

    def claim(self):
        """Short transactional claim. Reclaim abandoned processing jobs after worker loss."""
        with self.sessions.begin() as db:
            # The stale timeout covers crashes; optimistic FOR UPDATE SKIP LOCKED supports multi-workers.
            t = now()
            query = (select(AutonomousScanJob).where(
                ((AutonomousScanJob.state == 'queued') & (AutonomousScanJob.next_attempt_at <= t)) |
                ((AutonomousScanJob.state == 'processing') & (AutonomousScanJob.updated_at <= t-timedelta(hours=2))))
                .order_by(AutonomousScanJob.next_attempt_at).limit(1).with_for_update(skip_locked=True))
            job = db.scalar(query)
            if not job:
                return None
            job.state='processing'; job.attempts+=1; job.updated_at=t
            return {'id':job.id,'household_id':job.household_id,'media_id':job.media_id,'attempts':job.attempts}

    def finish(self, job_id, state, message='', room_id=None, review_summary=None):
        if state not in {'completed','held_unverified_room','failed','queued'}:
            raise ValueError('Invalid job state')
        with self.sessions.begin() as db:
            job = db.get(AutonomousScanJob, job_id)
            if job is None:
                raise LookupError('Unknown job')
            job.state=state; job.updated_at=now()
            if room_id is not None:
                job.room_id=room_id
            job.message=str(message)[:160]
            if review_summary is not None:
                job.review_summary=review_summary
            if state == 'queued':
                job.next_attempt_at=now()+timedelta(minutes=min(60, 2**min(job.attempts,5)))

    def process_one(self, *, media, bridge, build_pipeline, scan):
        """Process one claimed job; no persistent task write on ambiguous room matching."""
        job=self.claim()
        if not job:
            return None
        try:
            refs=self.rooms(job['household_id'])
            if not refs:
                # The first original photograph is its own anchor. Independent visual
                # verification and a supported room category precede enrollment.
                current = media.get_image(job['household_id'], job['media_id'])
                if current is None:
                    self.finish(job['id'], 'failed', 'Image no longer available')
                    return 'failed'
                result = scan(household_id=job['household_id'], media_id=job['media_id'],
                    reference_media_id=job['media_id'], media=media, bridge=bridge,
                    build_pipeline=build_pipeline, require_room_category=True)
                if result.get('status') != 'reviewed':
                    self.finish(job['id'], 'held_unverified_room', 'Room category could not be verified')
                    return 'held_unverified_room'
                room_id = self.enroll(job['household_id'], job['media_id'], result.get('room_category'))
                self.finish(job['id'], 'completed', room_id=room_id,
                    review_summary={**result.get('review_summary', {}),
                                    'created_count': len(result.get('created', [])),
                                    'existing_count': len(result.get('existing', []))})
                return 'completed'
            # Choose a reference ONLY after independent two-model image matching.
            from app.vision.autonomous_api import verify_room_pair
            current=media.get_image(job['household_id'],job['media_id'])
            if current is None:
                self.finish(job['id'],'failed','Image no longer available')
                return 'failed'
            current_info, current_image=current
            enrolled_reference = next((ref for ref in refs
                if ref['reference_media_id'] == job['media_id']), None)
            if enrolled_reference is not None:
                matching = [enrolled_reference]
            else:
                matching=[]
                vision, _, _ = build_pipeline()
                independent=getattr(vision,'independent',None)
                try:
                    for ref in refs:
                        stored=media.get_image(job['household_id'],ref['reference_media_id'])
                        if stored:
                            info, data=stored
                            if verify_room_pair(vision,data,info.content_type,current_image,current_info.content_type):
                                matching.append(ref)
                finally:
                    if independent is not None and hasattr(independent.client,'close'):
                        independent.client.close()
            if len(matching)!=1:
                self.finish(job['id'],'held_unverified_room','No unique verified room match')
                return 'held_unverified_room'
            ref=matching[0]
            result=scan(household_id=job['household_id'],media_id=job['media_id'],
                reference_media_id=ref['reference_media_id'], media=media,
                bridge=bridge,build_pipeline=build_pipeline)
            status='completed' if result.get('status')=='reviewed' else 'held_unverified_room'
            if status == 'completed':
                self.set_room_category(job['household_id'], ref['room_id'], result.get('room_category'))
            self.finish(job['id'],status,room_id=ref['room_id'],
                review_summary={**result.get('review_summary', {}),
                                'created_count': len(result.get('created', [])),
                                'existing_count': len(result.get('existing', []))}
                    if status == 'completed' else None)
            return status
        except Exception as exc:
            logger.warning('Scan job %s attempt %s failed: %s', job['id'], job['attempts'], _failure_summary(exc))
            retrying = job['attempts'] < 3
            self.finish(job['id'], 'queued' if retrying else 'failed',
                        _user_failure_message(exc, retrying=retrying))
            return 'retry_scheduled' if job['attempts']<3 else 'failed'

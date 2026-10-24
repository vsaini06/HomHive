"""Durable, opt-in image scan outbox; never invent room associations."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import DateTime, Integer, String, UniqueConstraint, Index, select
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def now():
    return datetime.now(timezone.utc)


class AutonomousRoomRecord(Base):
    __tablename__ = 'autonomous_rooms'
    household_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    room_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    reference_media_id: Mapped[str] = mapped_column(String(128), nullable=False)
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
    __table_args__ = (UniqueConstraint('household_id','media_id',name='uq_autonomous_job_media'),
                     Index('ix_autonomous_job_pending','state','next_attempt_at'))


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

    def enroll(self, household_id: str, media_id: str):
        with self.sessions.begin() as db:
            previous = db.scalar(select(AutonomousRoomRecord).where(
                AutonomousRoomRecord.household_id == household_id,
                AutonomousRoomRecord.reference_media_id == media_id))
            if previous:
                return previous.room_id
            room_id = 'reference:' + media_id
            db.add(AutonomousRoomRecord(household_id=household_id, room_id=room_id,
                reference_media_id=media_id, created_at=now()))
            # Previously unassigned jobs become eligible for fresh identity verification.
            held = db.scalars(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id,
                AutonomousScanJob.state == 'held_unverified_room')).all()
            for job in held:
                job.state = 'queued'
                job.next_attempt_at = now()
                job.updated_at = now()
                job.message = ''
            return room_id

    def rooms(self, household_id):
        with self.sessions() as db:
            rows = db.scalars(select(AutonomousRoomRecord).where(AutonomousRoomRecord.household_id == household_id)).all()
            return [{'room_id':r.room_id,'reference_media_id':r.reference_media_id} for r in rows]

    def jobs(self, household_id):
        with self.sessions() as db:
            rows = db.scalars(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id).order_by(AutonomousScanJob.updated_at.desc()).limit(100)).all()
            return [{'id':r.id,'media_id':r.media_id,'room_id':r.room_id,'state':r.state,
                'attempts':r.attempts,'message':r.message} for r in rows]

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

    def finish(self, job_id, state, message='', room_id=None):
        if state not in {'completed','held_unverified_room','failed','queued'}:
            raise ValueError('Invalid job state')
        with self.sessions.begin() as db:
            job = db.get(AutonomousScanJob, job_id)
            if job is None:
                raise LookupError('Unknown job')
            job.state=state; job.room_id=room_id; job.updated_at=now()
            job.message=str(message)[:160]
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
                self.finish(job['id'],'held_unverified_room','Enroll a physical room before scanning')
                return 'held_unverified_room'
            # Choose a reference ONLY after independent two-model image matching.
            from app.vision.autonomous_api import verify_room_pair
            current=media.get_image(job['household_id'],job['media_id'])
            if current is None:
                self.finish(job['id'],'failed','Image no longer available')
                return 'failed'
            current_info, current_image=current
            matching=[]
            vision, _, _ = build_pipeline()
            independent=getattr(vision,'independent',None)
            try:
                for ref in refs:
                    if ref['reference_media_id'] == job['media_id']:
                        matching.append(ref)
                        continue
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
            self.finish(job['id'],status,room_id=ref['room_id'])
            return status
        except Exception:
            # Do not leak provider payloads or credentials. Bound retry count.
            self.finish(job['id'],'queued' if job['attempts']<3 else 'failed','Processing needs retry' if job['attempts']<3 else 'Review required')
            return 'retry_scheduled' if job['attempts']<3 else 'failed'

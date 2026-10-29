"""Durable, opt-in image scan outbox; never invent room associations."""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, Index, select
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.services.demo_scene_identity import verified_demo_scene, base_room_category

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
                label = room_category.strip()[:120] if room_category else None
                if label:
                    peers = db.scalars(select(AutonomousRoomRecord).where(
                        AutonomousRoomRecord.household_id == household_id)).all()
                    existing_labels = {r.room_category.casefold() for r in peers if r.room_category}
                    if label.casefold() in existing_labels:
                        base = base_room_category(label)
                        number = 2
                        while f"{base} {number}" in existing_labels:
                            number += 1

                        base_display = label.rsplit(" ", 1)[0] if label.rsplit(" ", 1)[-1].isdigit() else label
                        label = f"{base_display} {number}"[:120]
                db.add(AutonomousRoomRecord(household_id=household_id, room_id=room_id,
                    reference_media_id=media_id, room_category=label,
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

    def assign_existing_room(self, household_id: str, media_id: str, room_id: str):
        """A person can resolve an ambiguous photo against their own room reference."""
        with self.sessions.begin() as db:
            room = db.get(AutonomousRoomRecord, (household_id, room_id))
            if room is None:
                raise LookupError("Selected room does not exist in this household")
            job = db.scalar(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id,
                AutonomousScanJob.media_id == media_id).with_for_update())
            if job is None:
                raise LookupError("Scan not found")
            if job.state != 'held_unverified_room':
                raise ValueError("Only a scan awaiting room identification can be linked")
            job.room_id = room_id
            job.state = 'queued'
            job.attempts = 0
            job.next_attempt_at = now()
            job.updated_at = now()
            job.message = ''
            return {'room_id': room_id, 'job_id': job.id}

    def rooms(self, household_id):
        with self.sessions() as db:
            rows = db.scalars(select(AutonomousRoomRecord).where(AutonomousRoomRecord.household_id == household_id)).all()
            return [{'room_id': r.room_id, 'reference_media_id': r.reference_media_id,
                     'room_category': r.room_category,
                     'room_category_source': r.room_category_source,
                     'created_at': r.created_at.isoformat()} for r in rows]

    def recent_room_views(self, household_id: str, *, limit_per_room: int = 2) -> dict[str, list[str]]:
        """Previously completed room-linked photos are trusted visual anchors, not category guesses."""
        with self.sessions() as db:
            rows = db.scalars(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == household_id,
                AutonomousScanJob.state == 'completed',
                AutonomousScanJob.room_id.is_not(None)).order_by(
                AutonomousScanJob.updated_at.desc()).limit(100)).all()
            views: dict[str, list[str]] = {}
            for job in rows:
                bucket = views.setdefault(job.room_id, [])
                if job.media_id not in bucket and len(bucket) < limit_per_room:
                    bucket.append(job.media_id)
            return views

    def set_room_category(self, household_id: str, room_id: str, category: str | None):
        if not category:
            return
        with self.sessions.begin() as db:
            room = db.get(AutonomousRoomRecord, (household_id, room_id))
            if room and room.room_category_source != 'user_confirmed':


                if room.room_category and (base_room_category(room.room_category) == base_room_category(category)
                    or room.room_category.rsplit(" ", 1)[-1].isdigit()):
                    return
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

            t = now()
            query = (select(AutonomousScanJob).where(
                ((AutonomousScanJob.state == 'queued') & (AutonomousScanJob.next_attempt_at <= t)) |
                ((AutonomousScanJob.state == 'processing') & (AutonomousScanJob.updated_at <= t-timedelta(hours=2))))
                .order_by(AutonomousScanJob.next_attempt_at).limit(1).with_for_update(skip_locked=True))
            job = db.scalar(query)
            if not job:
                return None
            job.state='processing'; job.attempts+=1; job.updated_at=t
            return {'id':job.id,'household_id':job.household_id,'media_id':job.media_id,'attempts':job.attempts, 'room_id':job.room_id}

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

    def process_one(self, *, media, bridge, build_pipeline, scan, after_completed=None):
        """Process one claimed job; no persistent task write on ambiguous room matching."""
        job=self.claim()
        if not job:
            return None
        try:
            refs=self.rooms(job['household_id'])
            current_media = media.get_image(job['household_id'], job['media_id'])
            if current_media is None:
                self.finish(job['id'], 'failed', 'Image no longer available')
                return 'failed'
            from app.services.autonomous_objects import ObjectRegistry
            object_registry = ObjectRegistry(self.sessions)
            current_demo = verified_demo_scene(current_media[1])
            from app.coordination.scene_focus import classify_scene_focus

            known_object = bool(current_demo and classify_scene_focus([], None, current_demo.get('category'))['focus'] == 'object')
            if known_object:
                result = scan(household_id=job['household_id'], media_id=job['media_id'],
                    reference_media_id=job['media_id'], media=media, bridge=bridge,
                    build_pipeline=build_pipeline, object_probe=True, object_registry=object_registry)
                if result.get('status') == 'reviewed' and result.get('object_id') and result.get('review_summary', {}).get('scene_focus', {}).get('focus') == 'object':
                    self.finish(job['id'], 'completed', review_summary={**result.get('review_summary', {}),
                        'created_count': len(result.get('created', [])),
                        'existing_count': len(result.get('existing', []))})
                    if after_completed is not None:
                        try: after_completed(job['id'])
                        except Exception as exc:
                            logger.warning('Post-scan coordination unavailable: %s', type(exc).__name__)
                    return 'completed'

                self.finish(job['id'], 'held_unverified_room', 'Object could not be verified')
                return 'held_unverified_room'
            if not refs:


                current = media.get_image(job['household_id'], job['media_id'])
                if current is None:
                    self.finish(job['id'], 'failed', 'Image no longer available')
                    return 'failed'
                result = scan(household_id=job['household_id'], media_id=job['media_id'],
                    reference_media_id=job['media_id'], media=media, bridge=bridge,
                    build_pipeline=build_pipeline, require_room_category=True)
                if result.get('status') == 'held_object_scope':
                    object_result = scan(household_id=job['household_id'], media_id=job['media_id'],
                        reference_media_id=job['media_id'], media=media, bridge=bridge,
                        build_pipeline=build_pipeline, object_probe=True, object_registry=object_registry)
                    if object_result.get('status') == 'reviewed' and object_result.get('object_id'):
                        self.finish(job['id'], 'completed', review_summary={**object_result.get('review_summary', {}),
                            'created_count': len(object_result.get('created', [])),
                            'existing_count': len(object_result.get('existing', []))})
                        if after_completed is not None:
                            try: after_completed(job['id'])
                            except Exception as exc: logger.warning('Post-scan coordination unavailable: %s', type(exc).__name__)
                        return 'completed'
                if result.get('status') != 'reviewed':
                    self.finish(job['id'], 'held_unverified_room', 'Room or object could not be verified')
                    return 'held_unverified_room'
                room_id = self.enroll(job['household_id'], job['media_id'], result.get('room_category'))
                self.finish(job['id'], 'completed', room_id=room_id,
                    review_summary={**result.get('review_summary', {}),
                                    'created_count': len(result.get('created', [])),
                                    'existing_count': len(result.get('existing', []))})
                if after_completed is not None:
                    try:
                        after_completed(job['id'])
                    except Exception as exc:
                        logger.warning('Post-scan coordination unavailable: %s', type(exc).__name__)
                return 'completed'

            from app.vision.autonomous_api import verify_room_pair
            current=media.get_image(job['household_id'],job['media_id'])
            if current is None:
                self.finish(job['id'],'failed','Image no longer available')
                return 'failed'
            current_info, current_image=current


            current_demo = verified_demo_scene(current_image)
            known_ref_scenes = {}
            if current_demo:
                views_for_demo = self.recent_room_views(job['household_id'])
                for room in refs:
                    for reference_id in [room['reference_media_id'], *views_for_demo.get(room['room_id'], [])]:
                        stored = media.get_image(job['household_id'], reference_id)
                        entry = verified_demo_scene(stored[1]) if stored else None
                        if entry:
                            known_ref_scenes.setdefault(room['room_id'], []).append(entry)
            selected_reference = next((ref for ref in refs if ref['room_id'] == job['room_id']), None)
            user_confirmed_existing = bool(selected_reference and
                selected_reference['reference_media_id'] != job['media_id'])
            enrolled_reference = next((ref for ref in refs
                if ref['reference_media_id'] == job['media_id']), None)
            if selected_reference is not None:
                matching = [selected_reference]
            elif enrolled_reference is not None:
                matching = [enrolled_reference]
            elif current_demo and any(
                entry['family'] == current_demo['family']
                for entries in known_ref_scenes.values() for entry in entries
            ):

                matching = [ref for ref in refs if any(
                    entry['family'] == current_demo['family']
                    for entry in known_ref_scenes.get(ref['room_id'], []))]
                if len(matching) != 1:
                    self.finish(job['id'], 'held_unverified_room', 'Conflicting demo family ownership')
                    return 'held_unverified_room'
            elif current_demo and all(
                base_room_category(ref['room_category']) != base_room_category(current_demo['category'])
                or (known_ref_scenes.get(ref['room_id']) and all(
                    entry['family'] != current_demo['family']
                    for entry in known_ref_scenes[ref['room_id']]))
                for ref in refs
            ):



                result = scan(household_id=job['household_id'], media_id=job['media_id'],
                    reference_media_id=job['media_id'], media=media, bridge=bridge,
                    build_pipeline=build_pipeline, require_room_category=True)
                if result.get('status') != 'reviewed':
                    self.finish(job['id'], 'held_unverified_room', 'Room category could not be verified')
                    return 'held_unverified_room'
                label = current_demo['category']
                room_id = self.enroll(job['household_id'], job['media_id'], label)
                self.finish(job['id'], 'completed', room_id=room_id,
                    review_summary={**result.get('review_summary', {}),
                        'room_identity_source': 'verified_demo_new_scene',
                        'created_count': len(result.get('created', [])),
                        'existing_count': len(result.get('existing', []))})
                if after_completed is not None:
                    try:
                        after_completed(job['id'])
                    except Exception as exc:
                        logger.warning('Post-scan coordination unavailable: %s', type(exc).__name__)
                return 'completed'
            else:
                matching = []



                views = self.recent_room_views(job['household_id'])
                vision, _, _ = build_pipeline()
                independent = getattr(vision, 'independent', None)
                try:
                    for ref in refs:
                        candidates = [ref['reference_media_id']]
                        candidates.extend(media_id for media_id in views.get(ref['room_id'], [])
                                          if media_id not in candidates and media_id != job['media_id'])
                        for reference_id in candidates:
                            stored = media.get_image(job['household_id'], reference_id)
                            if stored:
                                info, data = stored
                                if verify_room_pair(vision, data, info.content_type,
                                                    current_image, current_info.content_type):
                                    matching.append(ref)
                                    break
                finally:
                    if independent is not None and hasattr(independent.client, 'close'):
                        independent.client.close()
            if len(matching)!=1:
                if not matching:
                    result = scan(household_id=job['household_id'], media_id=job['media_id'],
                        reference_media_id=job['media_id'], media=media, bridge=bridge,
                        build_pipeline=build_pipeline, object_probe=True, object_registry=object_registry)
                    if result.get('status') == 'reviewed' and result.get('object_id') and result.get('review_summary', {}).get('scene_focus', {}).get('focus') == 'object':
                        self.finish(job['id'], 'completed', review_summary={**result.get('review_summary', {}),
                            'created_count': len(result.get('created', [])),
                            'existing_count': len(result.get('existing', []))})
                        if after_completed is not None:
                            try: after_completed(job['id'])
                            except Exception as exc:
                                logger.warning('Post-scan coordination unavailable: %s', type(exc).__name__)
                        return 'completed'
                self.finish(job['id'],'held_unverified_room','No unique verified room or object match')
                return 'held_unverified_room'
            ref=matching[0]
            kwargs = dict(household_id=job['household_id'], media_id=job['media_id'],
                reference_media_id=ref['reference_media_id'], media=media,
                bridge=bridge, build_pipeline=build_pipeline, object_registry=object_registry)
            if user_confirmed_existing:
                kwargs['user_confirmed_room'] = True
            elif selected_reference is None and enrolled_reference is None:
                if current_demo and any(entry['family'] == current_demo['family']
                    for entry in known_ref_scenes.get(ref['room_id'], [])):
                    kwargs['trusted_demo_relationship'] = True
                else:
                    kwargs['verified_room_evidence'] = True
            result = scan(**kwargs)
            status='completed' if result.get('status')=='reviewed' else 'held_unverified_room'
            if status == 'completed':
                self.set_room_category(job['household_id'], ref['room_id'], result.get('room_category'))
            self.finish(job['id'],status,room_id=ref['room_id'],
                review_summary={**result.get('review_summary', {}),
                                'created_count': len(result.get('created', [])),
                                'existing_count': len(result.get('existing', []))}
                    if status == 'completed' else None)
            if status == 'completed' and after_completed is not None:
                try:
                    after_completed(job['id'])
                except Exception as exc:
                    logger.warning('Post-scan coordination unavailable: %s', type(exc).__name__)
            return status
        except Exception as exc:
            logger.warning('Scan job %s attempt %s failed: %s', job['id'], job['attempts'], _failure_summary(exc))
            retrying = job['attempts'] < 3
            self.finish(job['id'], 'queued' if retrying else 'failed',
                        _user_failure_message(exc, retrying=retrying))
            return 'retry_scheduled' if job['attempts']<3 else 'failed'

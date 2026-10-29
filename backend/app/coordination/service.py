"""Household planning from bounded, attributable signals, without AI calls.

A preferred time window is not proof of availability; a presence observation
is not proof that the resident is free. Only an explicit, unexpired FREE signal
can make a household task immediately eligible. Inconclusive inputs remain unknown.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone, time as daytime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from app.automation.context import current_presence
from app.services.autonomous_lifecycle import (
    AutonomousAvailabilityRecord, AutonomousTaskRecord, TaskState, AutonomousLifecycle,
)
from .models import ContextSignalRecord, QuietHoursRecord


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def set_availability(sessions: sessionmaker[Session], household_id: str, state: str,
                     *, ttl_minutes: int = 60, now: datetime | None = None) -> dict:
    if state not in ('FREE', 'BUSY', 'UNKNOWN') or type(ttl_minutes) is not int or not 1 <= ttl_minutes <= 240:
        raise ValueError('Choose a valid availability state and expiry')
    now = now or datetime.now(timezone.utc)
    with sessions.begin() as db:
        entry = db.get(ContextSignalRecord, (household_id, 'availability'))
        if entry is None:
            entry = ContextSignalRecord(household_id=household_id, kind='availability',
                state='UNKNOWN', source='manual', confidence=0, observed_at=now,
                expires_at=now, consent=False)
            db.add(entry)
        entry.state = state
        entry.confidence = 1 if state != 'UNKNOWN' else 0
        entry.source = 'manual'
        entry.observed_at = now
        entry.expires_at = now + timedelta(minutes=ttl_minutes) if state != 'UNKNOWN' else now
        entry.consent = state != 'UNKNOWN'
    return availability_status(sessions, household_id, now)


def availability_status(sessions: sessionmaker[Session], household_id: str,
                        now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    with sessions() as db:
        entry = db.get(ContextSignalRecord, (household_id, 'availability'))
        if entry is not None and entry.consent and aware(entry.expires_at) > now:
            return {'state': entry.state, 'source': entry.source,
                    'confidence': entry.confidence, 'expires_at': aware(entry.expires_at).isoformat()}
    return {'state': 'UNKNOWN', 'source': None, 'confidence': None, 'expires_at': None}


def set_quiet_hours(sessions: sessionmaker[Session], household_id: str, enabled: bool,
                    start: str, end: str, now: datetime | None = None,
                    timezone_name: str | None = None) -> dict:
    if type(enabled) is not bool:
        raise ValueError('Invalid quiet hours setting')
    try:
        if (len(start) != 5 or len(end) != 5 or
            daytime.fromisoformat(start).strftime('%H:%M') != start or
            daytime.fromisoformat(end).strftime('%H:%M') != end or start == end):
            raise ValueError
    except (TypeError, AttributeError, ValueError):
        raise ValueError('Quiet hours require distinct HH:MM times') from None
    now = now or datetime.now(timezone.utc)
    if timezone_name is not None:
        try:
            if len(timezone_name) > 64 or not timezone_name.strip():
                raise ValueError
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise ValueError('Choose a recognized time zone') from None
    with sessions.begin() as db:
        record = db.get(QuietHoursRecord, household_id)
        if record is None:
            schedule = db.get(AutonomousAvailabilityRecord, household_id)
            record = QuietHoursRecord(household_id=household_id, enabled=enabled,
                start_time=start, end_time=end, timezone=timezone_name or (schedule.timezone if schedule else 'UTC'), updated_at=now)
            db.add(record)
        record.enabled = enabled
        record.start_time = start
        record.end_time = end
        if timezone_name is not None:
            record.timezone = timezone_name
        record.updated_at = now
    return {'enabled': enabled, 'start_time': start, 'end_time': end, 'timezone': record.timezone}


def quiet_hours_active(local_clock: datetime, *, enabled: bool, start: str, end: str) -> bool:
    if not enabled:
        return False
    current = local_clock.time().replace(tzinfo=None)
    a, b = daytime.fromisoformat(start), daytime.fromisoformat(end)
    return a <= current < b if a < b else current >= a or current < b


def _remaining_preferred_minutes(local: datetime, work_window: dict | None) -> int:
    if work_window is None or local.weekday() not in work_window['weekdays']:
        return 0
    start = daytime.fromisoformat(work_window['start_time'])
    end = daytime.fromisoformat(work_window['end_time'])
    current = local.time().replace(tzinfo=None)
    if not start <= current < end:
        return 0
    end_at = datetime.combine(local.date(), end, tzinfo=local.tzinfo)
    return max(0, int((end_at - local).total_seconds() // 60))


def _plan_item(task: dict, presence: str, available: str, preferred_minutes: int,
               quiet: bool, priority: int, now: datetime) -> dict:
    duration = task['estimate_max'] if len(task['estimate_sources']) >= 2 else None


    noise = str((task.get('noise_level') or 'unknown')).lower()
    approval = task['confirmation_required'] and task.get('task_state') not in ('accepted', 'in_progress')
    reasons: list[str] = []
    if approval:
        status = 'BLOCKED'; reasons.append('Waiting for your approval before scheduling')
    elif presence == 'AWAY':
        status = 'BLOCKED'; reasons.append('A household member has reported being away')
    elif available == 'BUSY':
        status = 'DEFERRED'; reasons.append('You marked yourself busy')
    elif quiet and noise != 'quiet':
        status = 'DEFERRED'; reasons.append('Quiet hours are active; noise safety is not confirmed')
    elif presence != 'HOME':
        status = 'SOON'; reasons.append('Presence is unknown; a photo does not prove someone is home')
    elif available != 'FREE':
        status = 'SOON'; reasons.append('Home is not the same as available')
    elif duration is None:
        status = 'SOON'; reasons.append('Duration has not been independently supported')
    elif duration > preferred_minutes:
        status = 'DEFERRED'; reasons.append('Not enough time remains in your preferred window')
    else:
        status = 'NOW'; reasons.append('Confirmed home and free; duration fits the chosen work window')
    if duration is None:
        reasons.append('Estimated duration unknown; no unsupported scheduling promise')
    return {'task_id': task['task_id'], 'title': task['title'], 'room_id': task['room_id'],
        'priority': priority, 'status': status, 'reasons': reasons,
        'duration_min': task['estimate_min'] if duration is not None else None,
        'duration_max': duration, 'duration_sources': task['estimate_sources'] if duration is not None else [],
        'progress_percent': task['progress_percent'], 'remaining_work': task['remaining_work'],
        'source': 'corroborated_household_evidence', 'evaluated_at': now.isoformat()}


def coordination_plan(sessions: sessionmaker[Session], household_id: str,
                      now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    presence = current_presence(sessions, household_id, now)
    availability = availability_status(sessions, household_id, now)
    with sessions() as db:
        schedule = db.get(AutonomousAvailabilityRecord, household_id)
        quiet_pref = db.get(QuietHoursRecord, household_id)
        work = ({'timezone': schedule.timezone, 'start_time': schedule.start_time,
                 'end_time': schedule.end_time, 'weekdays': schedule.weekdays}
                if schedule else None)
        pref = {'enabled': quiet_pref.enabled, 'start_time': quiet_pref.start_time,
                'end_time': quiet_pref.end_time, 'timezone': quiet_pref.timezone} if quiet_pref else {
                'enabled': True, 'start_time': '22:00', 'end_time': '07:00', 'timezone': work['timezone'] if work else 'UTC'}
    timezone_name = work['timezone'] if work else pref['timezone']
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        zone = timezone.utc
        timezone_name = 'UTC'
    local = now.astimezone(zone)
    try:
        quiet_zone = ZoneInfo(pref['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        quiet_zone = timezone.utc
    quiet = quiet_hours_active(now.astimezone(quiet_zone), **{'enabled': pref['enabled'],
        'start': pref['start_time'], 'end': pref['end_time']})
    minutes = _remaining_preferred_minutes(local, work)
    pulse = AutonomousLifecycle(sessions).household_pulse(household_id)
    with sessions() as db:
        records = {t.id: t for t in db.scalars(select(AutonomousTaskRecord).where(
            AutonomousTaskRecord.household_id == household_id,
            AutonomousTaskRecord.state.notin_((TaskState.completed.value, TaskState.dismissed.value)))).all()}
        tasks = []
        for s in pulse['suggestions']:
            rec = records.get(s['task_id'])
            if not rec:
                continue
            payload = rec.task_payload or {}
            tasks.append(_plan_item({**s,
                'noise_level': payload.get('noise_level'),
                'confirmation_required': bool(payload.get('confirmation_required', False)),
                'task_state': rec.state},
                presence['state'], availability['state'], minutes, quiet, s['priority'], now))

    order = {'NOW': 0, 'SOON': 1, 'DEFERRED': 2, 'BLOCKED': 3}
    tasks.sort(key=lambda item: (order[item['status']], -item['priority'], item['task_id']))
    counts = {status: sum(item['status'] == status for item in tasks) for status in order}


    from app.services.autonomous_jobs import AutonomousScanJob
    latest_automatic = None
    with sessions() as db:
        recent = db.scalars(select(AutonomousScanJob).where(
            AutonomousScanJob.household_id == household_id,
            AutonomousScanJob.state == 'completed'
        ).order_by(AutonomousScanJob.updated_at.desc()).limit(25)).all()
        for scan in recent:
            record = (scan.review_summary or {}).get('automatic_coordination')
            if isinstance(record, dict) and record.get('status') in ('completed', 'failed'):
                latest_automatic = {'scan_id': scan.id, 'updated_at': scan.updated_at.isoformat(), **record}
                break
    return {'presence': presence, 'availability': availability,
        'quiet_hours': {**pref, 'active': quiet}, 'work_window': work,
        'timezone': timezone_name, 'preferred_minutes_remaining': minutes,
        'groups': counts, 'tasks': tasks, 'evaluated_at': now.isoformat(),
        'source_note': 'Manual context and persisted evidence; no live calendar, GPS, or email connection',
        'latest_automatic_coordination': latest_automatic}

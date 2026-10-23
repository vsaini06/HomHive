"""Presence is opt-in, expiring, and does not imply availability."""
from datetime import datetime, timezone, timedelta
from enum import Enum
from sqlalchemy.orm import Session, sessionmaker
from app.db.presence_record import PresenceRecord


class PresenceState(str, Enum):
    HOME = 'HOME'
    AWAY = 'AWAY'
    UNKNOWN = 'UNKNOWN'


class Feasibility(str, Enum):
    FEASIBLE = 'FEASIBLE'
    NOT_FEASIBLE = 'NOT_FEASIBLE'
    UNKNOWN = 'UNKNOWN'


def current_presence(sessions: sessionmaker[Session], household_id: str,
                     now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    with sessions() as session:
        item = session.get(PresenceRecord, household_id)
        if item is None:
            return {'state': PresenceState.UNKNOWN.value, 'source': None,
                    'expires_at': None, 'consent': False}
        expires = item.expires_at.replace(tzinfo=timezone.utc) if item.expires_at.tzinfo is None else item.expires_at
        valid = item.consent_granted and expires > now
        return {'state': item.state if valid else PresenceState.UNKNOWN.value,
                'source': item.signal_source if valid else None,
                'expires_at': expires.isoformat() if valid else None,
                'consent': bool(item.consent_granted)}


def update_presence(sessions: sessionmaker[Session], household_id: str,
                    state: PresenceState, reliability: float, ttl_minutes: int,
                    granted: bool, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if not 0 <= reliability <= 1 or not 1 <= ttl_minutes <= 1440:
        raise ValueError('Invalid presence reliability or expiration')
    with sessions.begin() as session:
        record = session.get(PresenceRecord, household_id)
        if record is None:
            record = PresenceRecord(household_id=household_id, signal_source='manual',
                state=PresenceState.UNKNOWN.value, reliability=0,
                consent_granted=False, updated_at=now, expires_at=now)
            session.add(record)
        record.state = state.value if granted else PresenceState.UNKNOWN.value
        record.reliability = reliability if granted else 0
        record.signal_source = 'manual'
        record.consent_granted = granted
        record.updated_at = now
        record.expires_at = now + timedelta(minutes=ttl_minutes) if granted else now
    return current_presence(sessions, household_id, now)


def household_feasibility(presence: str, *, explicitly_available: bool = False,
                          requires_home: bool = True) -> Feasibility:
    if requires_home and presence == PresenceState.AWAY.value:
        return Feasibility.NOT_FEASIBLE
    if not explicitly_available:
        return Feasibility.UNKNOWN
    if requires_home and presence != PresenceState.HOME.value:
        return Feasibility.UNKNOWN
    return Feasibility.FEASIBLE

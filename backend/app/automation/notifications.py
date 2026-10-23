"""Materialize, deduplicate, and reconcile in-app task suggestions."""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from app.db.notification_record import NotificationRecord
from app.db.task_record import TaskRecord
from app.db.task_mapping import to_task
from app.models import TaskStatus


def sync_household(session: Session, household_id: str, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    created = 0
    tasks = [to_task(record) for record in session.scalars(
        select(TaskRecord).where(TaskRecord.household_id == household_id)).all()]
    observed_keys = {t.task_key for t in tasks if
        not t.task_key.startswith('predictive:') and t.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}}
    for task in tasks:
        notification = session.get(NotificationRecord, (household_id, task.id))
        hidden = (task.status in {TaskStatus.DISMISSED, TaskStatus.COMPLETED}
            or task.metadata.get('user_reported_complete_at') is not None
            or task.task_key.startswith('predictive:')
            and task.task_key.removeprefix('predictive:') in observed_keys)
        deferred = task.metadata.get('deferred_until')
        from app.automation.verification import parse_time
        is_deferred = parse_time(deferred) is not None and parse_time(deferred) > now
        state = ('suppressed' if hidden else 'deferred' if is_deferred
                 else 'accepted' if task.metadata.get('accepted_at') else 'suggested')
        if notification is None:
            notification = NotificationRecord(household_id=household_id, task_id=task.id,
                state=state, created_at=now, updated_at=now,
                available_after=parse_time(deferred) if is_deferred else None,
                delivery_channel='in_app', delivery_status='available')
            session.add(notification)
            created += 1
        elif notification.state != state or notification.available_after != (parse_time(deferred) if is_deferred else None):
            notification.state = state
            notification.available_after = parse_time(deferred) if is_deferred else None
            notification.updated_at = now
    return created


def list_notifications(sessions: sessionmaker[Session], household_id: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    with sessions.begin() as session:
        sync_household(session, household_id, now)
        entries = session.scalars(select(NotificationRecord)
            .where(NotificationRecord.household_id == household_id)
            .order_by(NotificationRecord.updated_at.desc())).all()
        result = []
        for entry in entries:
            if entry.state == 'suppressed':
                continue
            if entry.available_after is not None:
                after = entry.available_after.replace(tzinfo=timezone.utc) if entry.available_after.tzinfo is None else entry.available_after
                if after > now:
                    continue
            task = session.get(TaskRecord, (household_id, entry.task_id))
            if task is None:
                continue
            parsed = to_task(task)
            result.append({'id': parsed.id, 'task_id': parsed.id,
                'title': parsed.description,
                'space': parsed.task_key.removeprefix('predictive:').split(':')[0],
                'estimated_minutes': parsed.estimated_effort_minutes,
                'state': entry.state, 'delivery': entry.delivery_status,
                'source_observation_id': parsed.source_observation_id,
                'verification_status': parsed.metadata.get('verification_status'),
                'created_at': entry.created_at.isoformat()})
        return result

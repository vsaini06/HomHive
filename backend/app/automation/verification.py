"""One verification decision from fresh, trusted household evidence."""
from datetime import datetime, timedelta, timezone

from app.models import Task, TaskStatus
from app.repositories.observation_storage import ObservationStorage
from app.services.reactive_tasks import TASK_TRIGGERS


def parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else None
    except ValueError:
        return None


def evaluate(task: Task, household_id: str, observations: ObservationStorage,
             now: datetime | None = None, *, retry_hours: int = 24, max_attempts: int = 3) -> Task:
    now = now or datetime.now(timezone.utc)
    done_at = parse_time(task.metadata.get('user_reported_complete_at'))
    if done_at is None:
        raise ValueError('Completion not reported')
    if task.metadata.get('verification_status') in {'verified_resolved', 'verified_persisting', 'expired'}:
        return task
    due_at = parse_time(task.metadata.get('verification_due_at'))
    if due_at is not None and due_at > now:
        return task
    source = (observations.find_observation(household_id, task.source_observation_id)
              if task.source_observation_id else None)
    evidence = None
    trigger = TASK_TRIGGERS.get(source.category) if source else None
    if source and trigger:
        candidates = [item for item in observations.list_observations(household_id)
            if item.id != source.id and item.timestamp > done_at
            and item.location == source.location and item.category == source.category
            and item.entity_id == source.entity_id
            and item.source.value == 'user_input' and item.confidence is not None
            and item.confidence >= trigger.min_confidence]
        evidence = max(candidates, key=lambda item: item.timestamp) if candidates else None
    if evidence is None or trigger is None:
        status = 'awaiting_evidence'
    elif evidence.value >= trigger.trigger_level:
        status = 'verified_persisting'
    else:
        status = 'verified_resolved'
    attempts = int(task.metadata.get('verification_attempts', 0)) + 1
    if status == 'awaiting_evidence' and attempts >= max_attempts:
        status = 'expired'
    meta = {**task.metadata, 'verification_status': status,
        'verification_checked_at': now.isoformat(),
        'verification_evidence_id': evidence.id if evidence else None,
        'verification_attempts': attempts}
    if status == 'awaiting_evidence':

        meta['verification_due_at'] = (now + timedelta(hours=retry_hours)).isoformat()
    else:
        meta['verification_due_at'] = None
    task.metadata = meta
    if status == 'verified_resolved':
        task.status = TaskStatus.COMPLETED
    return task

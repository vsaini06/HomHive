"""Durable, externally scheduled verification worker. Run with --once.

Schedule it with the OS or a deployment job runner. It deliberately never
claims that photo capture happened without an authorized external source.
"""
import argparse
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.automation.verification import evaluate, parse_time
from app.db.task_mapping import to_task, to_task_record
from app.db.task_record import TaskRecord
from app.automation.notifications import sync_household
from app.repositories.sqlalchemy_observation_repository import SQLAlchemyObservationRepository


def run_due(sessions: sessionmaker[Session], *, now: datetime | None = None,
            limit: int = 100) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    if limit < 1 or limit > 500:
        raise ValueError('limit must be 1 through 500')
    result = {'checked': 0, 'needs_evidence': 0, 'resolved': 0, 'persisting': 0, 'notifications_created': 0}
    observations = SQLAlchemyObservationRepository(sessions)
    # Lock and mutate in one transaction; Postgres SKIP LOCKED allows multiple
    # workers to divide the due rows rather than verify the same task twice.
    with sessions.begin() as session:
        statement = (select(TaskRecord)
            .where(TaskRecord.task_metadata['verification_due_at'].as_string() <= now.isoformat())
            .order_by(TaskRecord.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True))
        for record in session.scalars(statement).all():
            task = to_task(record)
            due = parse_time(task.metadata.get('verification_due_at'))
            if due is None or due > now or not task.metadata.get('user_reported_complete_at'):
                continue
            before = task.metadata.get('verification_status')
            evaluate(task, record.household_id, observations, now)
            after = task.metadata.get('verification_status')
            if before == after and after not in {'awaiting_evidence', 'not_due'}:
                continue
            updated = to_task_record(record.household_id, task)
            record.status = updated.status
            record.task_metadata = updated.task_metadata
            result['checked'] += 1
            if after in {'awaiting_evidence', 'expired'}:
                result['needs_evidence'] += 1
            elif after == 'verified_resolved':
                result['resolved'] += 1
            elif after == 'verified_persisting':
                result['persisting'] += 1
        # Materialize persistent in-app suggestions without requiring a browser
        # to call /intelligence/refresh or /notifications.
        households = session.scalars(select(TaskRecord.household_id).distinct()).all()
        for household_id in households:
            result['notifications_created'] += sync_household(session, household_id, now)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', required=True)
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    from app.config import load_local_environment
    from app.db.session import build_engine, build_session_factory
    load_local_environment()
    engine = build_engine()
    try:
        print(run_due(build_session_factory(engine), limit=args.limit))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()

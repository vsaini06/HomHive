"""Read-only release readiness check; never prints credentials or photo contents."""
from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import select
from app.config import load_local_environment
from app.db.base import Base
from app.db.session import build_engine, build_session_factory
from app.services.autonomous_jobs import AutonomousScanJob
from app.services.autonomous_lifecycle import AutonomousLifecycle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--household', required=True, help='Household ID already known to this operator')
    args = parser.parse_args()
    load_local_environment()
    engine = build_engine()
    try:
        sessions = build_session_factory(engine)
        lifecycle = AutonomousLifecycle(sessions)
        with sessions() as db:
            jobs = db.scalars(select(AutonomousScanJob).where(
                AutonomousScanJob.household_id == args.household).order_by(
                AutonomousScanJob.updated_at.desc()).limit(30)).all()
            counts = Counter(job.state for job in jobs)
            print('Recent scan status:', dict(counts))
            if jobs:
                latest = jobs[0]
                print('Latest scan:', latest.state, 'attempts:', latest.attempts)
                review = latest.review_summary or {}
                print('Review: room:', review.get('room_category') or 'unverified',
                      'proposals:', review.get('proposed_count'),
                      'approved:', review.get('approved_count'),
                      'created:', review.get('created_count'))
                print('Evidence statements:', len(review.get('evidence') or []))
        tasks = lifecycle.list_tasks(args.household)
        print('Tasks:', len(tasks), 'by state:', dict(Counter(task['status'] for task in tasks)))
        for task in tasks[-8:]:
            progress = task.get('progress') or {}
            print(' -', task['title'][:90], '|', task['status'], '| progress:',
                  f"{progress['percent']}%" if progress.get('percent') is not None else 'not observed',
                  '| research citations:', len(task.get('estimate_sources') or []))
        pulse = lifecycle.household_pulse(args.household)
        print('Active suggested work:', pulse['active_count'],
              '| independently verified complete:', pulse['verified_complete_count'])
        print('Unread in-app notifications:', sum(a['read_at'] is None for a in lifecycle.alerts(args.household)))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()

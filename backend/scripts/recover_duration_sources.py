"""Re-check legacy task durations against Tavily without trusting narrative-only estimates.

Default is read-only. --apply makes bounded billable searches and stores only
independently corroborated source URLs. Does not mark tasks completed or approve work.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from app.config import load_local_environment
from app.db.session import build_engine, build_session_factory
from app.services.autonomous_lifecycle import AutonomousTaskRecord
from app.services.effort_research import research_existing_task_duration
from app.coordination.auto_orchestration import _HAZARD


def main():
    parser = argparse.ArgumentParser(description='Recover independently supported durations for existing tasks')
    parser.add_argument('--household', help='Required if more than one household has active tasks')
    parser.add_argument('--apply', action='store_true', help='Use Tavily and persist verified sources; consumes credits')
    parser.add_argument('--limit', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.limit <= 5:
        parser.error('--limit must be between 1 and 5')
    load_local_environment()
    engine = build_engine()
    sessions = build_session_factory(engine)
    try:
        with sessions() as db:
            rows = db.scalars(select(AutonomousTaskRecord).where(
                AutonomousTaskRecord.state.notin_(['completed', 'dismissed']))).all()
            household_ids = sorted({row.household_id for row in rows})
        if not args.household and len(household_ids) != 1:
            parser.error('Multiple households found. Specify --household with the ID shown in your app.')
        household = args.household or household_ids[0]
        candidates = [row for row in rows if row.household_id == household and
            len((row.task_payload or {}).get('estimate_sources') or []) < 2 and
            not _HAZARD.search(row.title + ' ' + row.action)]
        print('Tasks missing independently verified duration URLs:', len(candidates))
        if not args.apply:
            print('Preview only. To research at most', args.limit, 'tasks using Tavily credits, add --apply.')
            return
        from app.research.provider import TavilyResearchProvider
        provider = TavilyResearchProvider()
        try:
            for entry in candidates[:args.limit]:
                with sessions.begin() as db:
                    task = db.get(AutonomousTaskRecord, (household, entry.id))
                    payload = dict(task.task_payload or {})
                    stamp = payload.get('duration_research_attempted_at')
                    if stamp:
                        try:
                            if datetime.now(timezone.utc) - datetime.fromisoformat(stamp).astimezone(timezone.utc) < timedelta(hours=24):
                                print('Skipped recently researched:', task.title)
                                continue
                        except ValueError:
                            pass
                    payload['duration_research_attempted_at'] = datetime.now(timezone.utc).isoformat()
                    task.task_payload = payload
                estimate = research_existing_task_duration(entry.title, entry.action, provider=provider)
                if estimate is None or len(estimate.source_urls) < 2:
                    print('No independently supported duration:', entry.title)
                    continue
                with sessions.begin() as db:
                    task = db.get(AutonomousTaskRecord, (household, entry.id))
                    if task is None or task.state in ('completed', 'dismissed'):
                        continue
                    payload = dict(task.task_payload or {})
                    if len(payload.get('estimate_sources') or []) < 2:
                        task.effort_min, task.effort_max = estimate.minimum_minutes, estimate.maximum_minutes
                        payload['estimate_sources'] = estimate.source_urls
                        payload['estimate_rationale'] = estimate.rationale
                        task.task_payload = payload
                        print('Grounded duration:', task.title, f'{estimate.minimum_minutes}-{estimate.maximum_minutes} minutes')
        finally:
            provider.close()
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()

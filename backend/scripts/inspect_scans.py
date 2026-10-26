"""Read-only report of stored scan jobs, spaces and tasks for one household.

Run from the backend folder: python -m scripts.inspect_scans --household <id>
Prints no credentials, prompts or provider payloads.
"""
from __future__ import annotations

import argparse
import json

from app.config import load_local_environment
from app.db.session import build_engine, build_session_factory
from app.services.autonomous_jobs import AutonomousJobService
from app.services.autonomous_lifecycle import AutonomousLifecycle


def main():
    parser = argparse.ArgumentParser(description="Inspect stored autonomous scan state")
    parser.add_argument("--household", required=True)
    args = parser.parse_args()
    load_local_environment()
    sessions = build_session_factory(build_engine())
    jobs = AutonomousJobService(sessions)
    report = {
        "spaces": jobs.rooms(args.household),
        "scan_jobs": jobs.jobs(args.household),
        "tasks": AutonomousLifecycle(sessions).list_tasks(args.household),
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()

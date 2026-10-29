"""Read-only live API smoke checks against the local HomHive server.

Does not trigger paid provider calls, create scans, or alter household state.
For paid multimodal testing use scripts/live_smoke.py separately.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def call(base: str, path: str, *, bearer: str | None = None, method: str = 'GET', payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Accept': 'application/json'}
    if bearer:
        headers['Authorization'] = f'Bearer {bearer}'
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(base + path, headers=headers, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, None


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only checks of authenticated HomHive APIs')
    parser.add_argument('--api', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.api)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}:
        parser.error('For credential safety, this test only connects to a local HTTP API')
    base = args.api.rstrip('/')
    tests = []

    def verify(label: str, path: str, token: str | None = None):
        status, _ = call(base, path, bearer=token)
        tests.append((label, status == 200, status))

    verify('Backend health', '/health')
    if not tests[0][1]:
        print('Backend health failed; start FastAPI before testing')
        return 1
    email = input('HomHive account email: ').strip()
    password = getpass.getpass('Password (hidden): ')
    status, login = call(base, '/auth/login', method='POST', payload={'email': email, 'password': password})
    password = None
    if status != 200 or not isinstance(login, dict) or not login.get('access_token') or not login.get('households'):
        print(f'Authentication failed: HTTP {status}')
        return 1
    print('Authenticated. Testing household-scoped read endpoints, without provider charges.')
    token = login['access_token']
    household = urllib.parse.quote(login['households'][0], safe='')
    prefix = f'/households/{household}'
    paths = {
        'Decision intelligence': '/coordination',
        'Presence context': '/presence',
        'Room inventory': '/autonomous-rooms',
        'Task inventory': '/autonomous-tasks',
        'Scan job history': '/autonomous-scan-jobs',
        'Durable alerts': '/autonomous-alerts',
        'Work window': '/autonomous-work-window',
        'Household pulse': '/autonomous-pulse',
    }
    for name, path in paths.items():
        verify(name, prefix + path, token)
    unauth_status, _ = call(base, prefix + '/coordination')
    tests.append(('Unauthenticated coordination rejected', unauth_status in (401, 403), unauth_status))
    for name, passed, code in tests:
        print(f'{"PASS" if passed else "FAIL"}  {name}: HTTP {code}')
    print(f'{sum(t[1] for t in tests)}/{len(tests)} endpoint checks passed')
    return 0 if all(passed for _, passed, _ in tests) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as err:
        print(f'API checks could not complete: {type(err).__name__}', file=sys.stderr)
        sys.exit(1)

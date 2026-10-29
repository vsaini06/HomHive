"""Live, billable provider contract checks for the HomHive demo environment.

Run from backend with the active venv and backend/.env configured:
    python scripts/live_provider_suite.py --image "..\\frontend\\public\\demo-library\\Original 1.jpg"

This script uses real external APIs and never prints credentials or raw provider output.
It does not persist HomHive tasks. Use live_smoke.py for the full API/worker path.
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _parse_json(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```(?:json)?\s*|\s*```$', '', candidate, flags=re.I).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError('invalid_json') from exc
    if not isinstance(value, dict):
        raise ValueError('json_not_object')
    return value


def _request(url: str, payload: dict, headers: dict[str, str], *, timeout: int) -> dict:
    req = Request(url, json.dumps(payload).encode('utf-8'),
                  headers={'Content-Type': 'application/json', 'Accept': 'application/json', **headers}, method='POST')
    try:
        with urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read(2 * 1024 * 1024))
    except HTTPError as exc:
        raise RuntimeError(f'http_{exc.code}') from None
    except URLError as exc:
        raise RuntimeError('connection_error') from exc
    if not isinstance(data, dict):
        raise ValueError('response_not_object')
    return data


def _image(image_path: Path) -> tuple[str, str]:
    if not image_path.is_file():
        raise FileNotFoundError('image_not_found')
    mime = mimetypes.guess_type(image_path.name)[0]
    if mime not in {'image/jpeg', 'image/png', 'image/webp'}:
        raise ValueError('unsupported_image_type')
    size = image_path.stat().st_size
    if not 0 < size <= 10 * 1024 * 1024:
        raise ValueError('image_size_out_of_range')
    return mime, base64.b64encode(image_path.read_bytes()).decode('ascii')


VISION_SYSTEM = (
    'You are checking a real household image for API integration testing. '
    'Return ONLY a JSON object with keys room_category (string or null) and '
    'visible_objects (array of 1 to 8 short strings). Describe only observable objects; '
    'do not invent tasks or people.'
)


def _validate_vision(raw: dict) -> dict:
    room = raw.get('room_category')
    objects = raw.get('visible_objects')
    if room is not None and not isinstance(room, str):
        raise ValueError('invalid_room_category')
    if not isinstance(objects, list) or not objects or not all(isinstance(v, str) and v.strip() for v in objects):
        raise ValueError('missing_visible_objects')
    return {'room': room or 'uncertain', 'object_count': len(objects)}


def test_nebius_vision(mime: str, b64: str, timeout: int) -> dict:
    key = os.environ['NEBIUS_API_KEY']
    model = os.environ.get('HOMHIVE_NEBIUS_VISION_MODEL', 'openbmb/MiniCPM-V-4_5')
    answer = _request('https://api.tokenfactory.nebius.com/v1/chat/completions', {
        'model': model, 'max_tokens': 450,
        'messages': [{'role': 'system', 'content': VISION_SYSTEM},
                     {'role': 'user', 'content': [{'type': 'text', 'text': 'Identify the visible household objects.'},
                                                {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}}]}],
    }, {'Authorization': f'Bearer {key}'}, timeout=timeout)
    choices = answer.get('choices')
    if not isinstance(choices, list) or not choices:
        raise ValueError('missing_choices')
    return _validate_vision(_parse_json(choices[0]['message']['content']))


def test_nebius_reasoning(mime: str, b64: str, timeout: int) -> dict:

    key = os.environ['NEBIUS_API_KEY']
    model = os.environ['NEBIUS_REASONING_MODEL']
    answer = _request('https://api.tokenfactory.nebius.com/v1/chat/completions', {
        'model': model, 'max_tokens': 300,
        'messages': [{'role': 'system', 'content': 'Return only JSON with field decision either defer or execute and field reason. Honor deterministic constraints.'},
                     {'role': 'user', 'content': 'A home-only task is pending, but user presence is AWAY. Should HomHive execute now?'}],
    }, {'Authorization': f'Bearer {key}'}, timeout=timeout)
    raw = _parse_json(answer['choices'][0]['message']['content'])
    if raw.get('decision') != 'defer' or not isinstance(raw.get('reason'), str):
        raise ValueError('reasoning_violated_away_constraint')
    return {'decision': 'defer', 'constraint_obeyed': True}


def test_openai_vision(mime: str, b64: str, timeout: int) -> dict:
    key = os.environ['OPENAI_API_KEY']
    model = os.environ.get('HOMHIVE_OPENAI_REVIEW_MODEL', 'gpt-4.1-mini')
    answer = _request('https://api.openai.com/v1/chat/completions', {
        'model': model, 'max_tokens': 450,
        'messages': [{'role': 'system', 'content': VISION_SYSTEM},
                     {'role': 'user', 'content': [{'type': 'text', 'text': 'Identify the visible household objects.'},
                                                {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}}]}],
    }, {'Authorization': f'Bearer {key}'}, timeout=timeout)
    choices = answer.get('choices')
    if not isinstance(choices, list) or not choices:
        raise ValueError('missing_choices')
    return _validate_vision(_parse_json(choices[0]['message']['content']))


def test_anthropic_vision(mime: str, b64: str, timeout: int) -> dict:
    key = os.environ['ANTHROPIC_API_KEY']
    model = os.environ.get('HOMHIVE_ANTHROPIC_REVIEW_MODEL', 'claude-sonnet-4-5-20250929')
    answer = _request('https://api.anthropic.com/v1/messages', {
        'model': model, 'max_tokens': 450, 'system': VISION_SYSTEM,
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'Identify the visible household objects.'},
            {'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': b64}}
        ]}],
    }, {'x-api-key': key, 'anthropic-version': '2023-06-01'}, timeout=timeout)
    content = answer.get('content')
    if not isinstance(content, list) or not content:
        raise ValueError('missing_content')
    text = '\n'.join(block.get('text', '') for block in content if isinstance(block, dict) and block.get('type') == 'text')
    return _validate_vision(_parse_json(text))


def test_tavily(mime: str, b64: str, timeout: int) -> dict:
    key = os.environ['TAVILY_API_KEY']
    answer = _request('https://api.tavily.com/search', {
        'query': 'official household cleaning guidance how to wash dishes by hand',
        'search_depth': 'basic', 'max_results': 3, 'include_answer': False,
        'include_images': False, 'include_raw_content': False,
    }, {'Authorization': f'Bearer {key}'}, timeout=timeout)
    results = answer.get('results')
    if not isinstance(results, list) or not results:
        raise ValueError('no_research_results')
    if not any(isinstance(r, dict) and isinstance(r.get('url'), str)
               and r['url'].startswith(('https://', 'http://')) and r.get('title') and r.get('content')
               for r in results):
        raise ValueError('unusable_research_evidence')
    return {'source_count': len(results), 'has_attributable_sources': True}


CHECKS = [
    ('Nebius vision', 'NEBIUS_API_KEY', test_nebius_vision),
    ('Nebius Nemotron reasoning', 'NEBIUS_REASONING_MODEL', test_nebius_reasoning),
    ('OpenAI vision', 'OPENAI_API_KEY', test_openai_vision),
    ('Anthropic vision', 'ANTHROPIC_API_KEY', test_anthropic_vision),
    ('Tavily research', 'TAVILY_API_KEY', test_tavily),
]


def run_checks(image: Path, timeout: int = 90, selected: set[str] | None = None, require_all: bool = False) -> int:
    from app.config import load_local_environment
    load_local_environment()
    mime, b64 = _image(image)
    problems = 0
    counts = {'PASS': 0, 'FAIL': 0, 'SKIP': 0}
    for label, key, callback in CHECKS:
        if selected is not None and label not in selected:
            continue
        missing = [v for v in ([key, 'NEBIUS_API_KEY'] if label == 'Nebius Nemotron reasoning' else [key]) if not os.getenv(v)]
        if missing:
            counts['SKIP'] += 1
            print(f'[SKIP] {label}: missing configuration: {", ".join(missing)}')
            if require_all:
                problems += 1
            continue
        t0 = time.perf_counter()
        try:
            detail = callback(mime, b64, timeout)
            counts['PASS'] += 1
            print(f'[PASS] {label}: {json.dumps(detail)} ({time.perf_counter()-t0:.1f}s)')
        except Exception as exc:
            counts['FAIL'] += 1
            problems += 1

            reason = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
            print(f'[FAIL] {label}: {reason[:100]} ({time.perf_counter()-t0:.1f}s)')
    print(f"RESULT: {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['SKIP']} SKIP")
    print('Provider API results confirm access and response shape, not HomHive task correctness.')
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Real billable Nebius, OpenAI, Anthropic, and Tavily API checks')
    parser.add_argument('--image', required=True, type=Path, help='Local JPEG/PNG/WebP photograph used for model tests')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--require-all', action='store_true', help='Missing provider settings count as failures')
    parser.add_argument('--only', choices=[x[0] for x in CHECKS], action='append', help='Repeat to select providers')
    args = parser.parse_args()
    if not 10 <= args.timeout <= 300:
        parser.error('timeout must be between 10 and 300 seconds')
    return run_checks(args.image, args.timeout, set(args.only) if args.only else None, args.require_all)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f'FAILED: {type(exc).__name__}: {str(exc)[:120]}', file=sys.stderr)
        sys.exit(1)

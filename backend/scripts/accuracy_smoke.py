"""Real, billable accuracy-first HomHive smoke tests without database writes.

Run from backend: python -m scripts.accuracy_smoke --images-dir <demo gallery> --limit 3
Actual provider calls exercise the same scene, verification, planning, review path
as the autonomous worker; model quality still requires independent ground truth.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from app.config import load_local_environment


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', action='append', type=Path, help='Individual source photograph, repeatable')
    parser.add_argument('--pair', nargs=2, action='append', type=Path, metavar=('REFERENCE', 'CURRENT'),
                        help='Explicit same-room original/variant pair; repeat to check multiple pairs')
    parser.add_argument('--images-dir', type=Path,
                        default=Path(__file__).resolve().parents[2] / 'frontend' / 'public' / 'demo-library')
    parser.add_argument('--pair-expected', action='append', choices=['addition', 'removal', 'condition', 'relocation'],
                        help='Known label for each --pair, in order. The model never receives these labels.')
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--report', type=Path, default=None)
    args = parser.parse_args(argv)
    if args.pair_expected and len(args.pair_expected) != len(args.pair or []):
        parser.error('Specify one --pair-expected for each --pair')
    if not 1 <= args.limit <= 40:
        parser.error('--limit must be between 1 and 40')
    load_local_environment()
    missing = [name for name in ('OPENAI_API_KEY','ANTHROPIC_API_KEY') if not os.getenv(name)]
    if missing:
        print('Missing configuration: ' + ', '.join(missing))
        return 2
    if args.image:
        images = args.image
    elif args.pair:
        images = []
    else:
        gallery = args.images_dir
        if not gallery.is_dir():
            print(f'Gallery not found: {gallery}; provide --image or --images-dir')
            return 2
        images = sorted(p for p in gallery.glob('Original [0-9]*.jpg') if '-thumb' not in p.name)[:args.limit]
    if (not images and not args.pair) or not all(p.is_file() for p in images) or not all(
        ref.is_file() and current.is_file() for ref, current in (args.pair or [])) :
        print('No valid photograph files found')
        return 2

    from openai import OpenAI
    import httpx
    from app.services.accuracy_models import AccuracyOpenAIJsonClient
    from app.services.open_world_live import (OpenWorldVision, OpenWorldPlanner,
        OpenWorldActionReviewer, AnthropicJsonClient, preview_verified_scene)

    api = OpenAI(timeout=180, max_retries=1)
    primary_model = os.getenv('HOMHIVE_ACCURACY_PRIMARY_MODEL', 'gpt-6-astra')
    reviewer_model = os.getenv('HOMHIVE_ACCURACY_REVIEW_MODEL', 'gpt-6.1-terra')
    claude_model = os.getenv('HOMHIVE_ACCURACY_ANTHROPIC_MODEL', 'claude-opus-5-5')
    primary = AccuracyOpenAIJsonClient(api, primary_model)
    secondary = AccuracyOpenAIJsonClient(api, reviewer_model)
    report = []
    def mime(path):
        return {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                'webp': 'image/webp'}.get(path.suffix.lower().lstrip('.'))
    with httpx.Client(timeout=180) as http:
        claude = AnthropicJsonClient(http, claude_model, os.environ['ANTHROPIC_API_KEY'],
                                     strict_structure=True)
        vision = OpenWorldVision(primary, claude, secondary)
        planner = OpenWorldPlanner(primary)
        judge = OpenWorldActionReviewer(claude)
        for path in images:
            start = time.monotonic()
            try:
                photo = path.read_bytes()
                media_type = mime(path)
                if not media_type:
                    raise ValueError('Unsupported image extension')
                result = preview_verified_scene(image=photo, media_type=media_type,
                    media_id='smoke:'+path.name, vision=vision, planner=planner, reviewer=judge)
                item = {'image': path.name, 'status': 'PASS', 'room': result.room_category,
                        'evidence': len(result.corroborated_evidence),
                        'actions': len(result.approved_actions),
                        'rejected_actions': len(result.rejected_actions),
                        'verification': result.verification,
                        'evidence_claims': [e.description for e in result.corroborated_evidence],
                        'approved_titles': [a.get('title') for a in result.approved_actions],
                        'model_audit': result.model_audit}
                print(f'[PASS] {path.name}: evidence={item["evidence"]} actions={item["actions"]} '
                      f'verification={item["verification"]}', flush=True)
            except Exception as exc:


                item = {'image': path.name, 'status': 'FAIL', 'error_type': type(exc).__name__}
                response = getattr(exc, 'response', None)
                status_code = getattr(response, 'status_code', None)
                if isinstance(status_code, int):
                    item['http_status'] = status_code
                print(f'[FAIL] {path.name}: {item["error_type"]}' +
                      (f' HTTP {status_code}' if isinstance(status_code, int) else ''), flush=True)
            item['elapsed_seconds'] = round(time.monotonic() - start, 2)
            report.append(item)
        for pair_index, (reference, current) in enumerate(args.pair or []):
            start = time.monotonic()
            label = f'{reference.name} -> {current.name}'
            try:
                ref_type, current_type = mime(reference), mime(current)
                if not ref_type or not current_type:
                    raise ValueError('Unsupported paired media format')
                reference_bytes, current_bytes = reference.read_bytes(), current.read_bytes()
                from app.vision.autonomous_api import verify_room_pair
                same = verify_room_pair(vision, reference_bytes, ref_type, current_bytes, current_type)
                if not same:
                    item = {'image': label, 'status': 'FAIL', 'error_type': 'UnverifiedPhysicalRoom'}
                else:
                    result = preview_verified_scene(
                        image=current_bytes, media_type=current_type, media_id='smoke:'+current.name,
                        vision=vision, planner=planner, reviewer=judge,
                        reference_image=reference_bytes, reference_media_type=ref_type)
                    pair_data = result.model_audit.get('paired_comparison', {})
                    item = {'image': label, 'status': 'PASS', 'room': result.room_category,
                            'evidence': len(result.corroborated_evidence),
                            'pair_evidence': [e.description for e in result.corroborated_evidence
                                              if e.id.startswith('p')],
                            'actions': len(result.approved_actions),
                            'approved_titles': [a.get('title') for a in result.approved_actions],
                            'model_audit': result.model_audit,
                            'verification': result.verification, 'pair_review_status': pair_data.get('status')}
                    expected = (args.pair_expected or [None] * len(args.pair or []))[pair_index]
                    if expected:
                        matched = any(row.get('change_type') == expected and row.get('accepted_as_action_evidence')
                                      for row in pair_data.get('proposed', []))
                        item['expected_change'] = expected
                        item['expected_change_verified'] = matched
                        if not matched:
                            item['status'] = 'FAIL'
                            item['error_type'] = 'ExpectedChangeNotCorroborated'
                print(f'[{item["status"]}] PAIR {label}: pair_evidence={len(item.get("pair_evidence", []))} '
                      f'actions={item.get("actions", 0)}', flush=True)
            except Exception as exc:
                item = {'image': label, 'status': 'FAIL', 'error_type': type(exc).__name__}
                response = getattr(exc, 'response', None)
                status_code = getattr(response, 'status_code', None)
                if isinstance(status_code, int):
                    item['http_status'] = status_code
                print(f'[FAIL] PAIR {label}: {item["error_type"]}', flush=True)
            item['elapsed_seconds'] = round(time.monotonic() - start, 2)
            report.append(item)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'models': {'primary':primary_model,
            'reviewer':reviewer_model,'anthropic':claude_model},'results':report},indent=2),encoding='utf-8')
        print(f'Report: {args.report}')
    passes = sum(r['status']=='PASS' for r in report)
    print(f'FINISHED: {passes}/{len(report)} integrated image checks completed. '
          'These checks verify provider integration, not correctness against labeled truth.')
    return 0 if passes == len(report) else 1


if __name__ == '__main__':
    sys.exit(main())

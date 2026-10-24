"""Explicit opt-in live scan: independently reviewed plans -> durable lifecycle.

A physical room is anchored to a user-selected reference photograph. Subsequent
scans require independent two-image continuity verification. The reference scan
itself is user enrollment, never an inferred match. Failures never write tasks.
"""
from __future__ import annotations

import base64
import hmac
import logging
from collections.abc import Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError

from app.services.autonomous_lifecycle import (
    AutonomousLifecycle, EvidenceReference, OutcomeVerdict, ReviewedOutcome, RoomContinuity,
)
from app.services.autonomous_scan_bridge import AutonomousScanBridge, ScanOutcomeReview, VerifiedScan
from app.services.open_world_live import preview_verified_scene
from app.services.open_world_planning import ActionProposal

logger = logging.getLogger(__name__)

class ScanRequest(BaseModel):
    reference_media_id: str = Field(min_length=1, max_length=128)


def _image_url(image: bytes, media_type: str):
    return {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{base64.b64encode(image).decode('ascii')}"}}


def _check_images(info, image, reference_info, reference_image):
    if not image or not reference_image or info.content_type not in {"image/jpeg", "image/png", "image/webp"} or reference_info.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Unsupported image format")


def verify_room_pair(vision, ref_image: bytes, ref_type: str, image: bytes, media_type: str) -> bool:
    """Two independent image-aware assessments; disagreement means no match."""
    instruction = ("Compare two images of household spaces. Answer ONLY JSON "
        '{"same_physical_room":boolean,"explanation":string}. '
        "A matching room CATEGORY is insufficient. Require stable structural fixtures, layout, "
        "and distinctive persistent landmarks. Different angles, lighting, moved objects, "
        "and changing clutter are possible. If ambiguous or insufficient, respond false.")
    primary = vision.primary.client.chat.completions.create(
        model=vision.primary.model,
        messages=[{"role":"system","content":instruction}, {"role":"user","content":[
            {"type":"text","text":"Reference image, followed by candidate image."},
            _image_url(ref_image, ref_type), _image_url(image, media_type)]}], max_tokens=500)
    from app.services.open_world_live import _read_json_text
    p = _read_json_text(primary.choices[0].message.content) if primary.choices and primary.choices[0].finish_reason != 'length' else {}
    client = vision.independent
    blocks = [
        {"type":"text","text":"Reference image:"},
        {"type":"image","source":{"type":"base64","media_type":ref_type,"data":base64.b64encode(ref_image).decode('ascii')}},
        {"type":"text","text":"Candidate image:"},
        {"type":"image","source":{"type":"base64","media_type":media_type,"data":base64.b64encode(image).decode('ascii')}},
    ]
    response = client.client.post("https://api.anthropic.com/v1/messages", json={
        "model":client.model,"max_tokens":500,"system":instruction,
        "messages":[{"role":"user","content":blocks}]},
        headers={"x-api-key":client.key,"anthropic-version":"2023-06-01"})
    response.raise_for_status()
    content = response.json()
    if content.get("stop_reason") == "max_tokens":
        return False
    a = _read_json_text("\n".join(part.get("text","") for part in content.get("content",[]) if part.get("type")=="text"))
    return p.get("same_physical_room") is True and a.get("same_physical_room") is True


def review_completion(independent, *, task: dict, image: bytes, media_type: str, evidence: list, media_id: str) -> ReviewedOutcome:
    instruction = ("Independently audit ONE existing household task against the CURRENT original photograph "
      "and corroborated visual facts. Respond ONLY JSON "
      '{"verdict":"completed|still_needed|partially_completed|inconclusive",'
      '"criterion_verified":boolean,"claim_ids":["e1"],"explanation":"..."}. '
      "Complete ONLY if this new photograph visibly proves the SPECIFIC criterion; clean-looking "
      "surroundings alone are not proof. cite at least one corroborated claim ID. "
      "If the relevant area is not visible, use inconclusive. If uncertain, do not complete.")
    result = independent.ask(instruction=instruction, payload={"task":task,
       "corroborated_evidence":[e.model_dump(mode="json") for e in evidence]},
       image=image, media_type=media_type, max_tokens=800)
    claim_ids = result.get('claim_ids')
    if not isinstance(claim_ids, list) or not claim_ids or not all(isinstance(c, str) for c in claim_ids):
        raise ValueError("Completion review missing corroborated claim IDs")
    known = {e.id for e in evidence}
    if not set(claim_ids).issubset(known):
        raise ValueError("Completion review cited unsupported claims")
    if type(result.get('criterion_verified')) is not bool:
        raise ValueError("Completion review missing boolean criterion")
    verdict = OutcomeVerdict(result['verdict'])
    explanation = result.get('explanation')
    if not isinstance(explanation, str) or len(explanation.strip()) < 12:
        raise ValueError("Missing independent reasoning")
    return ReviewedOutcome(task_id=task['id'], verdict=verdict,
        criterion_verified=result['criterion_verified'], reviewer_explanation=explanation[:1500],
        evidence=EvidenceReference(media_id=media_id, claim_ids=claim_ids,
            original_image_reviewed=True, independent_review_passed=True))


def run_autonomous_scan(*, household_id, media_id, reference_media_id, media, bridge, build_pipeline):
    current = media.get_image(household_id, media_id)
    reference = media.get_image(household_id, reference_media_id)
    if not current or not reference:
        raise LookupError("Media not found")
    info, image = current
    ref_info, ref_image = reference
    _check_images(info, image, ref_info, ref_image)
    # Reference media ID is an explicit user-enrolled anchor, not a room category.
    room_id = f"reference:{reference_media_id}"
    vision, planner, reviewer = build_pipeline()
    independent = getattr(vision, 'independent', None)
    try:
        if media_id != reference_media_id:
            same = verify_room_pair(vision, ref_image, ref_info.content_type, image, info.content_type)
            if not same:
                return {"status":"held_unverified_room","saved":False,"created":[],"existing":[],"completed":{},"approved_actions":0}
        room = RoomContinuity(physical_room_id=room_id, same_physical_room_verified=True,
            reason="Reference photograph user enrollment" if media_id == reference_media_id else "Two independent visual room comparisons")
        preview = preview_verified_scene(image=image, media_type=info.content_type, media_id=media_id,
            vision=vision, planner=planner, reviewer=reviewer)
        evidence = preview.corroborated_evidence
        # Finish outcome verification before ANY writes, including new discoveries.
        existing_tasks = [task for task in bridge.get_tasks(household_id)
            if task['room_id'] == room_id and task['status'] not in ('dismissed', 'completed')]
        verdicts = []
        if existing_tasks and evidence:
            for task in existing_tasks:
                verdicts.append(review_completion(independent, task=task, image=image,
                    media_type=info.content_type, evidence=evidence, media_id=media_id))
        completion = bridge.reconcile_verified_scan(household_id, ScanOutcomeReview(
            media_id=media_id, room=room, corroborated_evidence=evidence, outcomes=verdicts)) if verdicts else {}
        approved = [ActionProposal.model_validate(action) for action in preview.approved_actions]
        discovered = bridge.persist_verified_scan(household_id, VerifiedScan(
            media_id=media_id, corroborated_evidence=evidence, approved_actions=approved,
            independently_reviewed=True, original_media_reviewed=True, room=room))
        return {"status":"reviewed","saved":True,"created":discovered['created'],
            "existing":discovered['existing'],"completed":completion,
            "approved_actions":len(approved),"rejected_actions":preview.rejected_actions,
            "room_id":room_id}
    finally:
        if independent is not None and hasattr(independent.client, 'close'):
            independent.client.close()


def build_autonomous_router(media, household_tokens: Mapping[str, str], session_factory, build_pipeline, jobs=None):
    router = APIRouter(prefix="/households/{household_id}", tags=["autonomous-lifecycle"])
    bearer = HTTPBearer(auto_error=False)
    bridge = AutonomousScanBridge(AutonomousLifecycle(session_factory))
    def check(household_id: str, credentials: HTTPAuthorizationCredentials | None):
        expected = household_tokens.get(household_id)
        if expected is None or credentials is None or not hmac.compare_digest(credentials.credentials, expected):
            raise HTTPException(status_code=403, detail="Access denied")
    @router.post('/autonomous-rooms/{reference_media_id}', status_code=201)
    def enroll_room(household_id: str, reference_media_id: str,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        if jobs is None:
            raise HTTPException(status_code=503, detail='Autonomous queue disabled')
        if media.get_image(household_id, reference_media_id) is None:
            raise HTTPException(status_code=404, detail='Media not found')
        return {'room_id': jobs.enroll(household_id, reference_media_id), 'reference_media_id': reference_media_id}

    @router.get('/autonomous-rooms')
    def list_rooms(household_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return {'rooms': jobs.rooms(household_id) if jobs is not None else []}

    @router.get('/autonomous-scan-jobs')
    def list_scan_jobs(household_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return {'jobs': jobs.jobs(household_id) if jobs is not None else []}

    @router.get('/autonomous-tasks')
    def list_tasks(household_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        return {'tasks': bridge.get_tasks(household_id)}
    @router.post('/media/{media_id}/autonomous-scan')
    def scan(household_id: str, media_id: str, request: ScanRequest,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        check(household_id, credentials)
        try:
            return run_autonomous_scan(household_id=household_id, media_id=media_id,
                reference_media_id=request.reference_media_id, media=media,
                bridge=bridge, build_pipeline=build_pipeline)
        except LookupError:
            raise HTTPException(status_code=404, detail="Media not found")
        except Exception as exc:
            if isinstance(exc, ValidationError):
                logger.warning('Autonomous scan schema error: fields=%s', [
                    {'field':'.'.join(map(str,x['loc'])),'type':x['type']}
                    for x in exc.errors(include_input=False)])
            else:
                logger.warning('Autonomous scan held: error_type=%s', type(exc).__name__)
            raise HTTPException(status_code=503, detail="Autonomous scan incomplete; review before trusting task state") from exc
    return router
